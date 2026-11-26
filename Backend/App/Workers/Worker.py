"""The NEXTRON worker process: claims jobs and runs them, separately from the API.

Run from the repository root (as many as you like; they coordinate through PostgreSQL):
    .\\.venv\\Scripts\\python.exe -m Backend.App.Workers.Worker

Each worker registers itself in `workers`, then loops: recover jobs whose lease expired, claim the next job,
run it while a heartbeat thread renews the lease (and notices cancellation or a lost lease), repeat.
Ctrl+C / SIGTERM lets the current job finish, then exits and marks the worker STOPPED. A killed worker
leaves its job RUNNING with a lease that expires; any worker then recovers it.
"""

import logging
import os
import signal
import socket
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings, get_settings
from Backend.App.Contracts.ExecutionStates import JobState, JobType
from Backend.App.Orchestration.TMir import Recording
from Backend.App.Orchestration.TMir.Executors import ModuleExecutor
from Backend.App.Orchestration.TMir.Runner import LeaseLost, RunControl, Runner
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Workers import JobService
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Models import WorkerProcess
from Database.PostgreSQL.Session import create_session_factory

logger = logging.getLogger("nextron.worker")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Worker:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        storage: LocalStorage,
        *,
        worker_id: str | None = None,
        executors: dict[str, ModuleExecutor] | None = None,
    ):
        self.settings = settings
        self.factory = session_factory
        self.storage = storage
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.executors = executors
        self.stopping = threading.Event()

    # ── registration ──────────────────────────────────────────────────────────────────────
    def register(self) -> None:
        with self.factory() as session:
            session.merge(WorkerProcess(worker_id=self.worker_id, hostname=socket.gethostname(), pid=os.getpid(),
                                        version=self.settings.APP_VERSION, state="RUNNING", started_at=_now(), heartbeat_at=_now()))
            session.commit()

    def deregister(self) -> None:
        with self.factory() as session:
            session.execute(update(WorkerProcess).where(WorkerProcess.worker_id == self.worker_id)
                            .values(state="STOPPED", stopped_at=_now(), current_job_id=None))
            session.commit()

    def _touch(self, session: Session, job_id: uuid.UUID | None) -> None:
        session.execute(update(WorkerProcess).where(WorkerProcess.worker_id == self.worker_id)
                        .values(heartbeat_at=_now(), current_job_id=job_id, state="RUNNING"))
        session.commit()

    # ── one job ───────────────────────────────────────────────────────────────────────────
    def recover(self) -> list[uuid.UUID]:
        with self.factory() as session:
            recovered = JobService.recover_expired(session, self.settings, close_execution=Recording.interrupt)
        for job_id in recovered:
            logger.warning("Recovered job %s after its lease expired", job_id)
        return recovered

    def process_one(self) -> uuid.UUID | None:
        """Recovers expired leases, claims one job and runs it to an end. Returns the job ID, or None if idle."""
        self.recover()
        with self.factory() as session:
            job = JobService.claim(session, self.worker_id, lease_seconds=self.settings.JOB_LEASE_SECONDS)
            if job is None:
                self._touch(session, None)
                return None
            self._touch(session, job.id)
            job_id, job_type, number = job.id, job.job_type, job.display_number
        logger.info("Claimed %s (%s)", number, job_type)

        control = RunControl(self.worker_id)
        beating = threading.Event()
        beater = threading.Thread(target=self._heartbeat, args=(job_id, control, beating), name="job-heartbeat", daemon=True)
        beater.start()
        try:
            self._execute(job_id, job_type, control)
        finally:
            beating.set()
            beater.join(timeout=5)
            with self.factory() as session:
                self._touch(session, None)
        return job_id

    def _execute(self, job_id: uuid.UUID, job_type: str, control: RunControl) -> None:
        try:
            if job_type == JobType.INVESTIGATION_RUN.value:
                state = Runner(self.factory, self.storage, self.settings, control, actor=self.settings.OPERATOR_NAME,
                               executors=self.executors).run(job_id)
                logger.info("Job %s ended %s", job_id, state.value if state else "elsewhere (lease lost)")
                return
            with self.factory() as session:  # job types whose services are built in later steps
                job = JobService.get_job(session, job_id)
                JobService.finish(session, job, self.worker_id, JobState.FAILED,
                                  error={"code": "NO_HANDLER", "message": f"No worker handler exists for {job_type} in this build"})
        except LeaseLost:
            logger.warning("Lease on job %s lost", job_id)
        except Exception as exc:  # infrastructure failure: retry with backoff, or fail after the last attempt
            logger.exception("Job %s raised", job_id)
            with self.factory() as session:
                job = JobService.get_job(session, job_id)
                JobService.fail_or_retry(session, job, self.worker_id,
                                         {"code": "WORKER_ERROR", "message": f"{type(exc).__name__}: {exc}"[:2000]}, self.settings)

    def _heartbeat(self, job_id: uuid.UUID, control: RunControl, done: threading.Event) -> None:
        while not done.wait(self.settings.JOB_HEARTBEAT_SECONDS):
            try:
                with self.factory() as session:
                    beat = JobService.heartbeat(session, job_id, self.worker_id, lease_seconds=self.settings.JOB_LEASE_SECONDS)
                    self._touch(session, job_id)
            except Exception:  # a missed beat is survivable until the lease runs out
                logger.exception("Heartbeat for job %s failed", job_id)
                continue
            if beat.cancel_requested:
                control.cancel.set()
            if not beat.lease_held:
                control.lease_lost.set()
                return

    # ── the loop ──────────────────────────────────────────────────────────────────────────
    def run_forever(self) -> None:
        self.register()
        logger.info("Worker %s started", self.worker_id)
        try:
            while not self.stopping.is_set():
                try:
                    if self.process_one() is None:
                        self.stopping.wait(self.settings.WORKER_POLL_SECONDS)
                except Exception:  # database down, for example: keep the worker alive and try again
                    logger.exception("Worker loop error")
                    self.stopping.wait(max(self.settings.WORKER_POLL_SECONDS, 5))
        finally:
            try:
                self.deregister()
            except Exception:
                logger.exception("Could not record the worker as stopped")
            logger.info("Worker %s stopped", self.worker_id)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    engine = create_database_engine(settings.DATABASE_URL, EngineOptions(
        pool_size=3, max_overflow=2, pool_timeout_seconds=settings.DATABASE_POOL_TIMEOUT_SECONDS,
        connect_timeout_seconds=settings.DATABASE_CONNECT_TIMEOUT_SECONDS, application_name="nextron-worker",
    ))
    storage = LocalStorage(settings.STORAGE_ROOT)
    worker = Worker(settings, create_session_factory(engine), storage)

    def stop(signum, frame):  # noqa: ARG001
        logger.info("Stop requested; finishing the current job first")
        worker.stopping.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        worker.run_forever()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
