'use client';

/* /dashboard: the command centre. Everything shown is read from the API now: case and evidence
   counts, the most recently active investigations, their latest recorded events, and measured system
   health and the job queue. Capabilities that do not exist yet (forensic findings) say so instead of showing numbers. */
import Link from 'next/link';
import { ArrowRight, Plus, Search, Upload } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api } from '@/api';
import { useCaseStatistics, useCases, useDatabaseStatus, useEvidenceStatistics, useJobs, useLiveness, useReadiness, useStorageStatus } from '@/api/hooks';
import { Dot, Empty, ErrorState, Load, PageHead, SecHead, Skeleton, Unavailable } from '@/components/ui';
import { JobList, WorkerNotice } from '@/modules/jobs/Jobs';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { ago, bytes, eventDetail, eventLabel, eventTone, statusLabel, statusTone, toneColor } from '@/utils/labels';
import { useQueries } from './useQueries';

export default function Dashboard() {
  const { openPalette } = useWorkspace();
  const stats = useCaseStatistics();
  const evStats = useEvidenceStatistics();
  const recent = useCases({ sort_by: 'last_activity_at', sort_order: 'desc', page_size: 6 });
  const st = stats.data, ev = evStats.data;

  return <div className={s.page}>
    <PageHead title='Dashboard' desc='Active investigations, preserved evidence and system health, read live from the NEXTRON API.'>
      <button className={`${s.btn} ${s.ghost}`} onClick={openPalette}><Search size={15} />Search</button>
      {recent.data?.data[0] && <Link className={s.btn} href={paths.caseAddEvidence(recent.data.data[0].case_id)} title={`Add evidence to ${recent.data.data[0].case_number}`}><Upload size={15} />Add evidence</Link>}
      <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link>
    </PageHead>

    {stats.error && !st ? <ErrorState error={stats.error} onRetry={stats.reload} /> : <div className={p.statGrid} aria-label='Investigation and evidence counts'>
      <Stat label='Active investigations' value={st?.active_cases} href={paths.investigations('active')} note={st && `${st.total_cases} in total`} />
      <Stat label='Review required' value={st?.by_status.REVIEW_REQUIRED} href={paths.investigations('active')} note='Investigations waiting on a person' />
      <Stat label='Evidence preserved' value={ev?.total_evidence} href={paths.evidenceList()} note={ev && bytes(ev.total_bytes)} />
      <Stat label='Images · videos · audio' value={ev && `${ev.by_media_type.IMAGE} · ${ev.by_media_type.VIDEO} · ${ev.by_media_type.AUDIO}`} href={paths.evidenceList()} />
      <Stat label='Archived' value={st?.by_status.ARCHIVED} href={paths.investigations('archived')} />
    </div>}

    <div className={p.grid2} style={{ marginTop: 24 }}>
      <section className={s.panel} aria-label='Recent investigations'>
        <SecHead title='Recently active investigations'><Link href={paths.investigations()} className={s.secLink}>All <ArrowRight size={13} /></Link></SecHead>
        <Load q={recent} rows={4}>{page => page.data.length ? <ul className={s.list}>{page.data.map(c => <li key={c.case_id}>
          <Link className={p.caseRow} href={paths.case(c.case_id)} style={{ gridTemplateColumns: '88px minmax(0,1fr) auto 90px' }}>
            <b>{c.case_number}</b>
            <span className={p.rowMain}><b>{c.title}</b><small>{c.evidence_count} evidence · {c.priority.toLowerCase()} priority</small></span>
            <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
            <span className={p.rowTime}>{ago(c.last_activity_at)}</span>
          </Link></li>)}</ul>
          : <Empty title='No investigations yet' action={<Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />Create the first one</Link>}>Create an investigation, then add the media you need to examine.</Empty>}</Load>
      </section>

      <div className={p.stack}>
        <HealthPanel />
        <JobsPanel />
      </div>
    </div>

    <div className={p.grid2} style={{ marginTop: 24 }}>
      <RecentActivity caseIds={recent.data?.data.slice(0, 5).map(c => c.case_id)} failed={!!recent.error && !recent.data} />
      <Unavailable title='Findings across investigations' modules={['NEX-INV']} step='plan Step 7'>
        <p>The image, video, audio and provenance engines now run on every upload; their findings, heatmaps and frame sheets are on each evidence item’s Analysis tab and each investigation’s Analysis tabs. A cross-investigation findings feed arrives with the review queue. No detector verdicts exist: no evaluated deepfake detector is installed.</p>
      </Unavailable>
    </div>
  </div>;
}

function Stat({ label, value, note, href }: { label: string; value: number | string | undefined; note?: string | false | undefined; href?: string }) {
  return <div className={p.stat}>
    <span>{label}</span>
    {value === undefined ? <Skeleton h={26} w={60} /> : <b>{value}</b>}
    {note && <small>{note}</small>}
    {href && value !== undefined && <Link href={href}>Open <ArrowRight size={12} style={{ verticalAlign: -1 }} /></Link>}
  </div>;
}

function HealthPanel() {
  const ready = useReadiness();
  const live = useLiveness();
  const db = useDatabaseStatus();
  const storage = useStorageStatus();
  const ok = ready.data && !ready.error;
  return <section className={s.panel} aria-label='System health'>
    <SecHead title='System health'><Link href={paths.system()} className={s.secLink}>Details <ArrowRight size={13} /></Link></SecHead>
    {ready.error?.unreachable ? <ErrorState error={ready.error} onRetry={ready.reload} /> : <dl className={s.kv}>
      <div><dt>API</dt><dd>{live.data ? <Dot tone='ok'>v{live.data.version} · {live.data.environment}</Dot> : live.error ? <Dot tone='alert'>Unreachable</Dot> : '…'}</dd></div>
      <div><dt>Readiness</dt><dd>{ok ? <Dot tone='ok'>Ready</Dot> : ready.error ? <Dot tone='alert'>Not ready</Dot> : '…'}</dd></div>
      <div><dt>PostgreSQL</dt><dd>{db.data ? <Dot tone={db.data.status === 'HEALTHY' ? 'ok' : 'gold'}>{db.data.server_version} · {db.data.latency_ms} ms</Dot> : db.error ? <Dot tone='alert'>{db.error.code}</Dot> : '…'}</dd></div>
      <div><dt>Evidence storage</dt><dd>{storage.data ? <Dot tone='ok'>Writable · {bytes(storage.data.free_bytes)} free</Dot> : storage.error ? <Dot tone='alert'>{storage.error.code}</Dot> : '…'}</dd></div>
    </dl>}
  </section>;
}

function JobsPanel() {
  const jobs = useJobs({ page_size: 5 });
  const active = useJobs({ active: true, page_size: 1 });
  return <section className={s.panel} aria-label='Analysis jobs'>
    <SecHead title='Analysis jobs'>{active.data && <span className={s.cap}>{active.data.pagination.total_items} queued or running</span>}</SecHead>
    <WorkerNotice quietWhenAlive />
    <Load q={jobs} rows={3}>{r => r.data.length ? <JobList jobs={r.data} /> : <p className={s.cap}>No jobs yet. Uploading evidence queues an investigation run for it.</p>}</Load>
  </section>;
}

/* Latest events from the most recently active investigations (there is no global event feed yet). */
function RecentActivity({ caseIds, failed }: { caseIds?: string[]; failed: boolean }) {
  const results = useQueries(caseIds?.map(id => ({ key: `case:${id}:summary`, fn: () => api.cases.summary(id) })) ?? []);
  const loading = !caseIds || results.some(r => r.status === 'loading' && !r.data);
  const events = results.flatMap(r => r.data ? r.data.recent_events.map(e => ({ e, c: r.data!.case })) : [])
    .sort((a, b) => b.e.sequence - a.e.sequence).slice(0, 8);
  return <section className={s.panel} aria-label='Recent activity'>
    <SecHead title='Recent activity'><span className={s.cap}>from the 5 most recently active investigations</span></SecHead>
    {failed ? <p className={s.cap}>Activity could not be loaded.</p> : loading ? <Skeleton h={160} r={12} /> : events.length ? <ol className={s.feed} style={{ padding: '4px 0' }}>
      {events.map(({ e, c }) => <li key={e.event_id} style={{ color: toneColor[eventTone(e.event_type)] }}>
        <time>{ago(e.occurred_at)}</time>
        <p><Link href={e.evidence_id ? paths.evidence(e.evidence_id, 'timeline') : paths.caseEvents(c.case_id)}>{eventLabel(e.event_type)}</Link><small><span className={s.mono}>{c.case_number}</span> · {eventDetail(e.event_type, e.payload) ?? c.title}</small></p>
      </li>)}
    </ol> : <p className={s.cap}>No recorded activity yet.</p>}
  </section>;
}
