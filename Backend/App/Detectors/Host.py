"""The detector host: pretrained models run in their own child process, never in the API or the worker.

Why a separate process:
  * model code from third-party repositories and pickle-format weights stay out of the process that holds
    database connections and evidence storage paths;
  * a model that hangs is killed after its timeout, and one that crashes is restarted, without taking the worker down;
  * the model stays loaded between requests (loading takes seconds), so each request costs only inference.

Protocol: one JSON object per line. The worker sends {"id", "detector", "path"} (an image path, or a 16 kHz mono
float32 .npy file for speech); the host answers {"id", "ok": true, "score", "seconds"} or {"id", "ok": false,
"error"}. The child is started with `-I` (isolated mode: no user site-packages, no current-directory imports).

Run the host by hand for diagnostics:  .\\.venv\\Scripts\\python.exe -m Backend.App.Detectors.Host
"""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from Backend.App.Config import PROJECT_ROOT

DETECTORS = {
    "CommunityForensics": ("Backend.App.Detectors.ImageDetectors", "CommunityForensics", {}),
    "Spai": ("Backend.App.Detectors.ImageDetectors", "Spai", {}),
    "SSL-AASIST-DF": ("Backend.App.Detectors.SpeechDetectors", "SslAasist", {"variant": "DF"}),
    "SSL-AASIST-LA": ("Backend.App.Detectors.SpeechDetectors", "SslAasist", {"variant": "LA"}),
}


def _pins() -> dict:
    from Backend.App.Detectors import Manifest

    return {"CommunityForensics": Manifest.COMMUNITY_FORENSICS, "Spai": Manifest.SPAI,
            "SSL-AASIST-DF": Manifest.SSL_AASIST_DF, "SSL-AASIST-LA": Manifest.SSL_AASIST_LA}


def detector_parameters(settings, module_id: str) -> dict:
    """The detector a module would use and its pinned weights, without starting the host (for input fingerprints)."""
    if not getattr(settings, "DETECTORS_ENABLED", False):
        return {"detector": None}
    name = {"NEX-IMG": settings.IMAGE_DETECTOR, "NEX-AUD": settings.SPEECH_DETECTOR}.get(module_id)
    if not name:
        return {"detector": None}
    pin = _pins().get(name)
    return {"detector": name, "detector_sha256": pin.sha256 if pin else None}


class DetectorUnavailable(RuntimeError):
    """The detector could not be loaded (weights missing or not matching their pin) or the host is not running."""


class DetectorFailed(RuntimeError):
    """The detector ran but did not produce a score for this input (error or timeout)."""


@dataclass(frozen=True)
class DetectorInfo:
    name: str
    version: str
    licence: str
    trained_on: str


# ── child side ───────────────────────────────────────────────────────────────────────────────

def _serve() -> None:
    import importlib

    import numpy as np

    loaded: dict = {}
    out = sys.stdout
    sys.stdout = sys.stderr  # anything a model prints goes to the log, never into the protocol stream
    for line in sys.stdin:
        request = json.loads(line)
        reply: dict = {"id": request.get("id")}
        try:
            name = request["detector"]
            if name not in DETECTORS:
                raise LookupError(f"unknown detector {name!r}; known: {sorted(DETECTORS)}")
            if name not in loaded:
                module, cls, kwargs = DETECTORS[name]
                loaded[name] = getattr(importlib.import_module(module), cls)(**kwargs)
            detector = loaded[name]
            if request.get("op") == "info":
                reply |= {"ok": True, "info": {"name": detector.name, "version": detector.version, "licence": detector.licence,
                                               "trained_on": detector.trained_on}}
            else:
                t0 = time.perf_counter()
                if hasattr(detector, "score_samples"):
                    score = detector.score_samples(np.load(request["path"], allow_pickle=False))
                else:
                    score = detector.score(request["path"])
                reply |= {"ok": True, "score": float(score), "seconds": round(time.perf_counter() - t0, 4)}
        except Exception as exc:  # reported to the caller, which records it on the module result
            reply |= {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "unavailable": type(exc).__name__ in ("IntegrityError", "LookupError")}
        out.write(json.dumps(reply) + "\n")
        out.flush()


# ── worker side ──────────────────────────────────────────────────────────────────────────────

class DetectorHost:
    """A child process serving detector requests one at a time (thread-safe; restarted after a crash or timeout)."""

    def __init__(self, *, python: str = sys.executable, startup_timeout: float = 120.0):
        self.python = python
        self.startup_timeout = startup_timeout
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._info: dict[str, DetectorInfo] = {}

    def _start(self) -> subprocess.Popen:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        env["HF_HUB_OFFLINE"] = "1"       # the host never downloads anything: weights are pinned files on disk
        env["TRANSFORMERS_OFFLINE"] = "1"
        self._process = subprocess.Popen(
            [self.python, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from Backend.App.Detectors.Host import _serve; _serve()",
             str(PROJECT_ROOT)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env, cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return self._process

    def _kill(self) -> None:
        if self._process is not None:
            try:
                self._process.kill()
                self._process.wait(timeout=10)
            except Exception:  # already gone
                pass
        self._process = None

    def close(self) -> None:
        with self._lock:
            self._kill()

    def _request(self, payload: dict, timeout: float) -> dict:
        with self._lock:
            process = self._process if self._process and self._process.poll() is None else self._start()
            payload = payload | {"id": uuid.uuid4().hex}
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            box: dict = {}
            reader = threading.Thread(target=lambda: box.setdefault("line", process.stdout.readline()), daemon=True)
            reader.start()
            reader.join(timeout)
            if reader.is_alive() or not box.get("line"):
                self._kill()  # hung or crashed: the next request starts a fresh host
                raise DetectorFailed(f"the detector did not answer within {timeout:g} s" if reader.is_alive() else "the detector process exited")
            reply = json.loads(box["line"])
            if reply.get("id") != payload["id"]:
                self._kill()
                raise DetectorFailed("the detector process answered out of order")
            return reply

    def info(self, detector: str) -> DetectorInfo:
        if detector not in self._info:
            reply = self._request({"op": "info", "detector": detector}, self.startup_timeout)
            if not reply["ok"]:
                raise DetectorUnavailable(reply["error"])
            self._info[detector] = DetectorInfo(**reply["info"])
        return self._info[detector]

    def score(self, detector: str, path: Path, *, timeout: float) -> tuple[float, float]:
        """(score, seconds). Loading counts against the first request's time, so the first call waits for startup too."""
        self.info(detector)
        reply = self._request({"op": "score", "detector": detector, "path": str(path)}, timeout)
        if not reply["ok"]:
            raise (DetectorUnavailable if reply.get("unavailable") else DetectorFailed)(reply["error"])
        return reply["score"], reply["seconds"]


_shared: DetectorHost | None = None


def shared_host() -> DetectorHost:
    global _shared
    if _shared is None:
        _shared = DetectorHost()
    return _shared


if __name__ == "__main__":
    _serve()
