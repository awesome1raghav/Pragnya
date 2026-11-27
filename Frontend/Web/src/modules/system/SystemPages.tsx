'use client';

/* /system, /system/health and /system/logs: the operational context, kept off the investigative pages. The overview
   leads with one readiness tile per dependency (API, database, storage, workers, graph projection, detectors); details
   are one click down. Every value is a measurement the API just made or a fact it reports; nothing is estimated. */
import Link from 'next/link';
import { motion } from 'framer-motion';
import { RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { API_BASE } from '@/api';
import { useDatabaseStatus, useJobs, useLiveness, useModules, useReadiness, useStorageStatus, useSystemConfig, useWorkers } from '@/api/hooks';
import { request } from '@/api/http';
import { useQuery } from '@/api/query';
import sy from './system.module.css';
import { useLive } from '@/api/live';
import { Dot, ErrorState, Load, PageHead, SecHead, Unavailable } from '@/components/ui';
import { paths } from '@/config/routes';
import { useSystemState } from '@/layouts/SystemStatus';
import { ago, bytes, moduleStatusLabel, moduleStatusTone, utc, type Tone } from '@/utils/labels';

const Tabs = ({ on }: { on: 'all' | 'health' | 'logs' }) => <nav className={`${s.seg} ${s.subTabs}`} aria-label='System sections' style={{ marginBottom: 24 }}>
  <Link href={paths.system()} aria-selected={on === 'all'}>Overview</Link><Link href={paths.systemHealth()} aria-selected={on === 'health'}>Health checks</Link><Link href={paths.systemLogs()} aria-selected={on === 'logs'}>Logs</Link>
</nav>;

type Projection = { consumer: string; configured: boolean; reachable: boolean | null; lag_events: number; nodes: number | null; relationships: number | null; error: string | null };
type Tile = { key: string; label: string; tone: Tone; value: string; note?: string };

export function SystemOverview() {
  const st = useSystemState();
  const live = useLiveness();
  const db = useDatabaseStatus();
  const storage = useStorageStatus();
  const workers = useWorkers();
  const cfg = useSystemConfig();
  const proj = useQuery('system:projections', () => request<Projection[]>('/system/projections'), { refreshMs: 30_000 });
  const modules = useModules();
  const refresh = () => { st.q.reload(); live.reload(); db.reload(); storage.reload(); workers.reload(); proj.reload(); };
  const neo = proj.data?.[0];
  const tiles: Tile[] = [
    { key: 'api', label: 'API', tone: live.data ? 'ok' : live.error ? 'alert' : 'mute', value: live.data ? `v${live.data.version}` : live.error ? 'Unreachable' : '…', note: live.data?.environment },
    { key: 'db', label: 'Database', tone: db.data ? (db.data.status === 'HEALTHY' ? 'ok' : 'gold') : db.error ? 'alert' : 'mute', value: db.data ? `${db.data.latency_ms} ms` : db.error ? db.error.code.toLowerCase().replace(/_/g, ' ') : '…', note: db.data ? `PostgreSQL ${db.data.server_version} · migration ${db.data.migrations.current.join(', ')}` : undefined },
    { key: 'storage', label: 'Evidence storage', tone: storage.data ? 'ok' : storage.error ? 'alert' : 'mute', value: storage.data ? `${bytes(storage.data.free_bytes)} free` : storage.error ? 'Not writable' : '…', note: storage.data ? 'writable, originals read-only' : undefined },
    { key: 'workers', label: 'Workers', tone: workers.data ? (workers.data.alive ? 'ok' : 'gold') : 'mute', value: workers.data ? `${workers.data.alive} running` : '…', note: workers.data && !workers.data.alive ? 'queued jobs wait for one' : 'heartbeating' },
    { key: 'graph', label: 'Graph projection', tone: !neo || !neo.configured ? 'mute' : neo.reachable ? (neo.lag_events ? 'gold' : 'ok') : 'gold', value: !neo ? '…' : !neo.configured ? 'Off' : neo.reachable ? (neo.lag_events ? `${neo.lag_events} behind` : 'Up to date') : 'Unreachable', note: neo?.reachable ? `${neo.nodes} nodes · Neo4j` : neo?.configured ? 'evidence intake is not affected' : 'Neo4j not configured' },
    { key: 'detectors', label: 'Detectors', tone: cfg.data ? (cfg.data.detectors.enabled ? 'ok' : 'mute') : 'mute', value: cfg.data ? (cfg.data.detectors.enabled ? 'On' : 'Off') : '…', note: cfg.data?.detectors.enabled ? [cfg.data.detectors.image, cfg.data.detectors.speech].filter(Boolean).join(' · ') : 'measurements still run' },
  ];
  return <div className={s.page}>
    <PageHead title='System' desc={st.tone === 'ok' ? 'Everything NEXTRON needs is ready. Measured just now.' : st.detail}><button className={s.btn} onClick={refresh}><RotateCcw size={15} />Check again</button></PageHead>
    <Tabs on='all' />
    <ul className={sy.tiles} aria-label='Readiness'>{tiles.map((t, i) => <motion.li key={t.key} className={sy.tile} data-tone={t.tone}
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, duration: .22, ease: [.22, 1, .36, 1] }}>
      <span className={sy.tileLabel}><i aria-hidden='true' />{t.label}</span><b>{t.value}</b>{t.note && <small>{t.note}</small>}
    </motion.li>)}</ul>
    <div className={p.grid2}>
      <div className={p.stack}>
        <WorkersPanel />
        <p className={s.cap}>The API and workers log errors with a request or job ID to their own consoles; a failed job keeps its error on the job (open the job monitor). There is no log API yet.</p>
      </div>
      <div className={p.stack}>
        <details className={`${s.panel} ${sy.details}`} aria-label='Backend connectivity'>
          <summary>Backend <small>{API_BASE}</small></summary>
          {live.error ? <ErrorState error={live.error} onRetry={live.reload} /> : <dl className={s.kv}>
            <div><dt>API base address</dt><dd className={s.mono} style={{ fontSize: 12 }}>{API_BASE}</dd></div>
            <div><dt>Service</dt><dd>{live.data?.service ?? '…'}</dd></div>
            <div><dt>Mode</dt><dd>Single local operator, no sign-in</dd></div>
          </dl>}
        </details>
        <details className={`${s.panel} ${sy.details}`} aria-label='Database'>
          <summary>PostgreSQL <small>authoritative store</small></summary>
          <Load q={db} rows={3}>{d => <dl className={s.kv}>
            <div><dt>Status</dt><dd><Dot tone={d.status === 'HEALTHY' ? 'ok' : 'gold'}>{d.status === 'HEALTHY' ? 'Healthy' : 'Reachable, not migrated to head'}</Dot></dd></div>
            <div><dt>Server</dt><dd>PostgreSQL {d.server_version} · {d.database_name}</dd></div>
            <div><dt>Schema migration</dt><dd>{d.migrations.current.join(', ') || 'none'} (head {d.migrations.head.join(', ')})</dd></div>
            <div><dt>Connection pool (this API process)</dt><dd>{d.connection_pool.checked_out} in use · {d.connection_pool.idle} idle · max {d.connection_pool.maximum}</dd></div>
            <div><dt>Last successful check</dt><dd>{utc(d.last_successful_check)}</dd></div>
          </dl>}</Load>
        </details>
        <details className={`${s.panel} ${sy.details}`} aria-label='Storage'>
          <summary>Evidence storage</summary>
          <Load q={storage} rows={2}>{st2 => <dl className={s.kv}>
            <div><dt>Backend</dt><dd>Local filesystem (read-only originals)</dd></div>
            <div><dt>Writable</dt><dd><Dot tone='ok'>Yes, probe write succeeded</Dot></dd></div>
            <div><dt>Free space</dt><dd>{bytes(st2.free_bytes)}</dd></div>
            <div><dt>Checked</dt><dd>{utc(st2.checked_at)}</dd></div>
          </dl>}</Load>
        </details>
        <details className={`${s.panel} ${sy.details}`} aria-label='Module availability'>
          <summary>Modules <small>{modules.data ? `${modules.data.modules.filter(m => m.status === 'IMPLEMENTED').length} implemented · ${modules.data.modules.filter(m => m.status === 'PARTIAL').length} partial` : ''}</small></summary>
          <Load q={modules} rows={4}>{cat => <ul className={s.miniList}>{cat.modules.map(m => <li key={m.module_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><span><span className={s.mono}>{m.module_id}</span> {m.name}</span><Dot tone={moduleStatusTone[m.status]}>{moduleStatusLabel[m.status]}</Dot></li>)}</ul>}</Load>
          <Link href={paths.intelligence()} className={s.secLink} aria-label='Module intelligence'>Module intelligence</Link>
        </details>
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
    <Unavailable title='Log access' modules={['Event outbox', 'Events API']} step='not built'>
      <p>No log API exists. The API and workers write their logs to the consoles where they run, or to the files they were started with; investigation and custody records are available, append-only, on each investigation’s Events tab and each evidence item’s Custody timeline.</p>
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
