'use client';

/* /system, /system/health and /system/logs. Every value is a measurement the API just made (readiness,
   PostgreSQL probe, storage probe) or a fact it reports (version, module status). Nothing here estimates
   CPU, memory or latency. Workers are reported from their own heartbeats; logs are not available yet. */
import Link from 'next/link';
import { RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { API_BASE } from '@/api';
import { useDatabaseStatus, useJobs, useLiveness, useModules, useReadiness, useStorageStatus, useWorkers } from '@/api/hooks';
import { useLive } from '@/api/live';
import { Dot, ErrorState, Load, PageHead, SecHead, Unavailable } from '@/components/ui';
import { paths } from '@/config/routes';
import { useSystemState } from '@/layouts/SystemStatus';
import { ago, bytes, moduleStatusLabel, moduleStatusTone, utc } from '@/utils/labels';

const Tabs = ({ on }: { on: 'all' | 'health' | 'logs' }) => <nav className={`${s.seg} ${s.subTabs}`} aria-label='System sections' style={{ marginBottom: 24 }}>
  <Link href={paths.system()} aria-selected={on === 'all'}>Overview</Link><Link href={paths.systemHealth()} aria-selected={on === 'health'}>Health checks</Link><Link href={paths.systemLogs()} aria-selected={on === 'logs'}>Logs</Link>
</nav>;

export function SystemOverview() {
  const st = useSystemState();
  const live = useLiveness();
  const db = useDatabaseStatus();
  const storage = useStorageStatus();
  const modules = useModules();
  const refresh = () => { st.q.reload(); live.reload(); db.reload(); storage.reload(); };
  return <div className={s.page}>
    <PageHead title='System' desc='Measured state of the NEXTRON backend and its dependencies.'><button className={s.btn} onClick={refresh}><RotateCcw size={15} />Check again</button></PageHead>
    <Tabs on='all' />
    <div className={p.statGrid} style={{ marginBottom: 20 }}>
      <div className={p.stat}><span>Overall</span><b style={{ fontSize: 18 }}><Dot tone={st.tone}>{st.label}</Dot></b><small>{st.detail}</small></div>
      <div className={p.stat}><span>API version</span><b style={{ fontSize: 18 }}>{live.data ? `v${live.data.version}` : live.error ? '—' : '…'}</b><small>{live.data?.environment ?? (live.error ? 'unreachable' : '')}</small></div>
      <div className={p.stat}><span>Database round trip</span><b style={{ fontSize: 18 }}>{db.data ? `${db.data.latency_ms} ms` : db.error ? '—' : '…'}</b><small>{db.data ? `measured ${utc(db.data.checked_at)}` : db.error?.code}</small></div>
      <div className={p.stat}><span>Evidence storage free</span><b style={{ fontSize: 18 }}>{storage.data ? bytes(storage.data.free_bytes) : storage.error ? '—' : '…'}</b><small>{storage.data ? 'local filesystem, writable' : storage.error?.code}</small></div>
    </div>
    <div className={p.grid2}>
      <div className={p.stack}>
        <section className={s.panel} aria-label='Backend connectivity'>
          <SecHead title='Backend' />
          {live.error ? <ErrorState error={live.error} onRetry={live.reload} /> : <dl className={s.kv}>
            <div><dt>API base address</dt><dd className={s.mono} style={{ fontSize: 12 }}>{API_BASE}</dd></div>
            <div><dt>Service</dt><dd>{live.data?.service ?? '…'}</dd></div>
            <div><dt>Mode</dt><dd>Single local operator, no sign-in</dd></div>
          </dl>}
        </section>
        <section className={s.panel} aria-label='Database'>
          <SecHead title='PostgreSQL (authoritative store)' />
          <Load q={db} rows={3}>{d => <dl className={s.kv}>
            <div><dt>Status</dt><dd><Dot tone={d.status === 'HEALTHY' ? 'ok' : 'gold'}>{d.status === 'HEALTHY' ? 'Healthy' : 'Reachable, not migrated to head'}</Dot></dd></div>
            <div><dt>Server</dt><dd>PostgreSQL {d.server_version} · {d.database_name}</dd></div>
            <div><dt>Schema migration</dt><dd>{d.migrations.current.join(', ') || 'none'} (head {d.migrations.head.join(', ')})</dd></div>
            <div><dt>Connection pool (this API process)</dt><dd>{d.connection_pool.checked_out} in use · {d.connection_pool.idle} idle · max {d.connection_pool.maximum}</dd></div>
            <div><dt>Last successful check</dt><dd>{utc(d.last_successful_check)}</dd></div>
          </dl>}</Load>
        </section>
        <section className={s.panel} aria-label='Storage'>
          <SecHead title='Evidence storage' />
          <Load q={storage} rows={2}>{st2 => <dl className={s.kv}>
            <div><dt>Backend</dt><dd>Local filesystem (read-only originals)</dd></div>
            <div><dt>Writable</dt><dd><Dot tone='ok'>Yes, probe write succeeded</Dot></dd></div>
            <div><dt>Free space</dt><dd>{bytes(st2.free_bytes)}</dd></div>
            <div><dt>Checked</dt><dd>{utc(st2.checked_at)}</dd></div>
          </dl>}</Load>
        </section>
      </div>
      <div className={p.stack}>
        <section className={s.panel} aria-label='Module availability'>
          <SecHead title='Module availability'><Link href={paths.intelligence()} className={s.secLink}>Intelligence</Link></SecHead>
          <Load q={modules} rows={4}>{cat => <ul className={s.miniList}>{cat.modules.map(m => <li key={m.module_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><span><span className={s.mono}>{m.module_id}</span> {m.name}</span><Dot tone={moduleStatusTone[m.status]}>{moduleStatusLabel[m.status]}</Dot></li>)}</ul>}</Load>
        </section>
        <WorkersPanel />
        <Unavailable title='Recent system errors' modules={['Observability']} step='plan Step 8'>
          <p>The API and workers log errors with a request or job ID to their consoles; failed jobs keep their error on the job (see the job monitor). A queryable system error record arrives with observability in Step 8.</p>
        </Unavailable>
      </div>
    </div>
  </div>;
}

export function SystemHealth() {
  const ready = useReadiness();
  const live = useLiveness();
  const checks = ready.data?.checks ?? (ready.error?.details as { checks?: Record<string, Record<string, unknown>> } | null)?.checks;
  return <div className={s.page}>
    <PageHead title='Health checks' desc='GET /health (the API process is running) and GET /health/ready (PostgreSQL is reachable and migrated, and evidence storage is writable). Rechecked every 15 seconds.'>
      <button className={s.btn} onClick={() => { ready.reload(); live.reload(); }}><RotateCcw size={15} />Check now</button>
    </PageHead>
    <Tabs on='health' />
    <div className={p.grid2}>
      <section className={s.panel} aria-label='Liveness'>
        <SecHead title='Liveness'>{live.data ? <Dot tone='ok'>Alive</Dot> : live.error ? <Dot tone='alert'>Down</Dot> : null}</SecHead>
        {live.error ? <ErrorState error={live.error} onRetry={live.reload} /> : <pre className={p.json}>{live.data ? JSON.stringify(live.data, null, 2) : '…'}</pre>}
      </section>
      <section className={s.panel} aria-label='Readiness'>
        <SecHead title='Readiness'>{ready.data && !ready.error ? <Dot tone='ok'>Ready</Dot> : ready.error ? <Dot tone='alert'>{ready.error.unreachable ? 'Unreachable' : 'Not ready'}</Dot> : null}</SecHead>
        {ready.error?.unreachable ? <ErrorState error={ready.error} onRetry={ready.reload} /> : checks ? <pre className={p.json}>{JSON.stringify(checks, null, 2)}</pre> : <p className={s.cap}>…</p>}
        {ready.error && !ready.error.unreachable && <p className={s.cap}>Request {ready.error.requestId ?? '—'} · {ready.error.code}</p>}
      </section>
    </div>
  </div>;
}

export function SystemLogs() {
  return <div className={s.page}>
    <PageHead title='Logs' desc='Operational log access for authorised operators, redacted of secrets.' />
    <Tabs on='logs' />
    <Unavailable title='Log access' modules={['Event outbox', 'Events API']} step='plan Step 3'>
      <p>No log API exists yet. Until then the API writes its log to the console where it runs; investigation and custody records are available, append-only, on each investigation’s Events tab and each evidence item’s Custody timeline.</p>
    </Unavailable>
  </div>;
}

function WorkersPanel() {
  const w = useWorkers();
  const queued = useJobs({ state: 'QUEUED', page_size: 1 });
  const running = useJobs({ state: 'RUNNING', page_size: 1 });
  const live = useLive();
  return <section className={s.panel} aria-label='Workers and job queue'>
    <SecHead title='Workers and job queue' />
    <Load q={w} rows={2}>{ws => <>
      <dl className={s.kv}>
        <div><dt>Workers alive</dt><dd><Dot tone={ws.alive ? 'ok' : 'alert'}>{ws.alive ? `${ws.alive} heartbeating` : 'none: queued jobs wait'}</Dot></dd></div>
        <div><dt>Queue</dt><dd>{queued.data?.pagination.total_items ?? '—'} queued · {running.data?.pagination.total_items ?? '—'} running</dd></div>
        <div><dt>Lease</dt><dd>{ws.lease_seconds} s (an unrenewed lease lets another worker recover the job)</dd></div>
        <div><dt>Live events</dt><dd>{live.state === 'live' ? <Dot tone='ok'>connected</Dot> : <Dot tone='gold'>{live.state}</Dot>}</dd></div>
      </dl>
      {ws.workers.length > 0 && <ul className={s.miniList}>{ws.workers.slice(0, 6).map(x => <li key={x.worker_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <span><span className={s.mono} style={{ fontSize: 12 }}>{x.worker_id}</span>{x.current_job_id ? ' · working' : ''}</span>
        <Dot tone={x.alive ? 'ok' : 'mute'}>{x.alive ? `heartbeat ${ago(x.heartbeat_at)}` : x.state === 'STOPPED' ? `stopped ${ago(x.stopped_at)}` : `silent since ${ago(x.heartbeat_at)}`}</Dot>
      </li>)}</ul>}
      {!ws.alive && <p className={s.cap}>Start a worker from the repository root: <code className={s.mono}>.venv\Scripts\python.exe -m Backend.App.Workers.Worker</code></p>}
    </>}</Load>
  </section>;
}
