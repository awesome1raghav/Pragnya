'use client';

/* Analysis views over T-MIR (plan Step 3): run analysis, then see, for every coordinated module, whether it ran,
   was skipped (and why), is not built yet, or failed, plus the findings current results carry. Nothing here
   computes or infers anything; it shows the stored plan, executions, result envelopes and findings. */
import Link from 'next/link';
import { useState } from 'react';
import { ArrowRight, Play } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, ApiError, type Artifact, type Evidence, type EvidenceAnalysis, type Finding, type FindingPayload, type PlanEntry } from '@/api';
import { useCaseEvidence, useCaseRuns, useEvidenceAnalysis, useModuleResults, useRun } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { Dot, Empty, Load, PageHead, SecHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { ago, execStateLabel, execStateTone, explain, ms, reasonLabel } from '@/utils/labels';
import { JobList, PlanTable, WorkerNotice } from '@/modules/jobs/Jobs';

function RunButton({ label, start, invalidates, disabled }: { label: string; start: () => Promise<{ job_number: string }>; invalidates: string[]; disabled?: boolean }) {
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { const job = await start(); notify(`Queued ${job.job_number}`); invalidate('jobs', ...invalidates); }
    catch (e) { notify(e instanceof ApiError ? e.message : 'The run could not be queued', 'alert'); }
    finally { setBusy(false); }
  };
  return <button className={`${s.btn} ${s.primary}`} onClick={go} disabled={busy || disabled}><Play size={14} />{busy ? 'Queuing…' : label}</button>;
}

export function ModuleTable({ a }: { a: EvidenceAnalysis }) {
  return <div className={p.planWrap}><table className={p.planTable}>
    <thead><tr><th>Module</th><th>State</th><th>Why / detail</th><th>Time</th></tr></thead>
    <tbody>{a.modules.map(m => {
      const x = m.latest;
      const why = x ? explain(x.state_reason, x.state_detail) : m.applicable ? 'not run yet' : 'does not apply to this media';
      return <tr key={m.module_id} data-dim={!x || x.state === 'SKIPPED' || x.state === 'UNAVAILABLE'}>
        <td><b className={s.mono} style={{ fontSize: 12 }}>{m.module_id}</b><small>{m.module_name}</small></td>
        <td>{x ? <Dot tone={execStateTone[x.state]}>{execStateLabel[x.state]}</Dot> : '—'}{x && x.attempt > 1 && <small>attempt {x.attempt}</small>}</td>
        <td>{why || '—'}{x?.tool_versions && Object.keys(x.tool_versions).length > 0 && <small>{Object.entries(x.tool_versions).map(([k, v]) => `${k}: ${v}`).join(' · ')}</small>}</td>
        <td data-nowrap>{x ? <>{ms(x.duration_ms)}<small>{ago(x.finished_at ?? x.created_at)}</small></> : '—'}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}

export function LatestRunCaseModules({ jobId }: { jobId: string }) {
  const run = useRun(jobId);
  return <section className={s.panel} aria-label='Case-level modules of the latest run'>
    <SecHead title='Case-level modules (latest run)' />
    <Load q={run} rows={3}>{r => <PlanTable plan={r.plan.filter(e => e.scope_kind !== 'EVIDENCE')} scopeLabel={e => (e.scope_kind === 'PAIR' ? 'pairs' : 'case')} />}</Load>
  </section>;
}

const where = (f: Finding) => {
  const { region, time_range } = f.payload as FindingPayload;
  if (time_range) return time_range.end_seconds - time_range.start_seconds < 0.01 ? `at ${time_range.start_seconds.toFixed(2)} s` : `${time_range.start_seconds.toFixed(2)}–${time_range.end_seconds.toFixed(2)} s`;
  if (region) return `region x ${region.x.toFixed(0)}% y ${region.y.toFixed(0)}% · ${region.w.toFixed(0)}×${region.h.toFixed(0)}%`;
  return null;
};

/** Findings with their measured location, score meaning, limitations and supporting artifacts (heatmaps, frames). */
export function FindingList({ findings, artifacts = [], image }: { findings: Finding[]; artifacts?: Artifact[]; image?: Evidence }) {
  const byId = new Map(artifacts.map(a => [a.artifact_id, a]));
  return <ul className={p.jobList}>{findings.map(f => {
    const payload = f.payload as FindingPayload;
    const support = (payload.supporting_artifact_ids ?? []).map(id => byId.get(id) ?? ({ artifact_id: id, mime_type: 'image/png' } as Artifact));
    const loc = where(f);
    return <li key={f.finding_id} className={p.jobRow} data-finding={f.finding_type}>
      <div>
        <b>{f.title}</b>
        <small>{f.module_id} · {f.assertion.toLowerCase()} · {f.finding_type}{loc ? ` · ${loc}` : ''}{f.score !== null ? ` · score ${f.score} (${f.score_kind?.toLowerCase().replace(/_/g, ' ')}, not a probability)` : ''}{f.confidence !== null ? ` · confidence ${f.confidence} (${f.confidence_basis})` : ''}</small>
        {f.description && <small>{f.description}</small>}
        {payload.limitations?.length > 0 && <small>Limits: {payload.limitations.join('; ')}</small>}
        {(support.some(a => a.mime_type === 'image/png') || (image && payload.region)) && <div className={p.findingMedia}>
          {image && payload.region && <figure className={p.regionFrame}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={api.evidence.previewUrl(image.evidence_id)} alt={`${image.filename} with the measured region marked`} />
            <i style={{ left: `${payload.region.x}%`, top: `${payload.region.y}%`, width: `${payload.region.w}%`, height: `${payload.region.h}%` }} aria-hidden='true' />
          </figure>}
          {support.filter(a => a.mime_type === 'image/png').map(a => <a key={a.artifact_id} href={api.analysis.artifactUrl(a.artifact_id)} target='_blank' rel='noreferrer' title={`${a.kind ?? 'artifact'} · SHA-256 ${a.sha256 ?? ''}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={api.analysis.artifactUrl(a.artifact_id)} alt={`${f.module_id} ${String(a.attributes?.method ?? a.kind ?? 'artifact').toLowerCase()} for this finding`} loading='lazy' />
          </a>)}
        </div>}
      </div>
    </li>;
  })}</ul>;
}

/* ── /investigations/:id/analysis/:branch: one engine across the case's evidence ── */
export function ModuleResultsPage({ caseId, moduleId }: { caseId: string; moduleId: string }) {
  const q = useModuleResults(caseId, moduleId);
  return <Load q={q} rows={4}>{m => {
    const relevant = m.evidence.filter(e => e.applicable);  // inapplicable media is skipped by T-MIR and would only add noise here
    if (!relevant.length) return <Empty title={`No evidence ${moduleId} applies to`}>{m.module_name} runs on {moduleId === 'NEX-PRV' ? 'formats that can carry C2PA credentials' : 'matching media'}; none is in this investigation yet.</Empty>;
    return <div className={p.stack}>{relevant.map(e => <section key={e.evidence_id} className={s.panel} aria-label={`${moduleId} result for ${e.evidence_number}`}>
      <SecHead title={<><Link href={paths.evidence(e.evidence_id, 'analysis')}>{e.evidence_number}</Link> <span className={s.muted}>· {e.filename}</span></>}>
        {e.latest ? <Dot tone={execStateTone[e.latest.state]}>{execStateLabel[e.latest.state]}{e.latest.state_reason ? ` · ${reasonLabel(e.latest.state_reason)}` : ''}</Dot> : <span className={s.cap}>not run yet</span>}
      </SecHead>
      {e.latest?.state_detail && <p className={s.cap}>{e.latest.state_detail}</p>}
      {e.findings.length ? <FindingList findings={e.findings} artifacts={e.artifacts} image={e.media_type === 'IMAGE' ? { evidence_id: e.evidence_id, filename: e.filename } as Evidence : undefined} />
        : <p className={s.cap}>{e.result_id ? 'This result has no findings.' : 'No current result.'}</p>}
      {e.artifacts.filter(a => a.mime_type === 'audio/wav').map(a => <p key={a.artifact_id} className={s.cap}>Working copy (16 kHz mono): <audio controls preload='none' src={api.analysis.artifactUrl(a.artifact_id)} /></p>)}
      {e.limitations.length > 0 && <p className={p.warnLine}>Limitations: {e.limitations.join(' · ')}</p>}
      {Object.keys(e.tool_versions).length > 0 && <p className={s.cap}>Tools: {Object.entries(e.tool_versions).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>}
    </section>)}</div>;
  }}</Load>;
}

/** Overview panel: the latest state of each module for one evidence item. */
export function EvidenceAnalysisSummary({ ev }: { ev: Evidence }) {
  const q = useEvidenceAnalysis(ev.evidence_id);
  return <section className={s.panel} aria-label='Analysis summary'>
    <SecHead title='Analysis'><Link href={paths.evidence(ev.evidence_id, 'analysis')} className={s.secLink}>Details <ArrowRight size={13} /></Link></SecHead>
    <Load q={q} rows={2}>{a => a.modules.some(m => m.latest) ? <dl className={s.kv}>{a.modules.map(m => <div key={m.module_id}>
      <dt>{m.module_name}</dt>
      <dd>{m.latest ? <Dot tone={execStateTone[m.latest.state]}>{execStateLabel[m.latest.state]}{m.latest.state_reason ? ` · ${reasonLabel(m.latest.state_reason)}` : ''}</Dot> : m.applicable ? 'not run yet' : 'not applicable'}</dd>
    </div>)}</dl> : <p className={s.cap}>{a.latest_job ? `${a.latest_job.job_number} is ${a.latest_job.state.toLowerCase()}.` : 'Not analysed yet.'}</p>}</Load>
  </section>;
}

/* ── /investigations/:id/analysis ── */
export function CaseAnalysisPage({ caseId, archived }: { caseId: string; archived: boolean }) {
  const runs = useCaseRuns(caseId);
  const evidence = useCaseEvidence(caseId);
  const latest = runs.data?.data[0] ?? null;
  const number = new Map((evidence.data?.data ?? []).map(e => [e.evidence_id, e.evidence_number]));
  const scope = (e: PlanEntry) => (e.scope_kind === 'EVIDENCE' ? number.get(e.evidence_id ?? '') ?? 'evidence' : e.scope_kind === 'PAIR' ? 'pairs' : 'case');
  return <>
    <div className={s.actions} style={{ marginBottom: 16 }}>
      <RunButton label='Analyse all evidence' disabled={archived || (evidence.data?.pagination.total_items ?? 0) === 0} start={() => api.runs.start(caseId)} invalidates={[`case:${caseId}`]} />
    </div>
    <WorkerNotice quietWhenAlive />
    <div className={p.stack}>
      <section className={s.panel} aria-label='Runs'>
        <SecHead title='Runs' count={runs.data?.pagination.total_items} />
        <Load q={runs} rows={2}>{r => r.data.length ? <JobList jobs={r.data.slice(0, 8)} /> : <Empty title='No runs yet'>Every upload queues a run for its evidence; you can also analyse all evidence at once.</Empty>}</Load>
      </section>
      {latest && <LatestPlan jobId={latest.job_id} scope={scope} />}
    </div>
  </>;
}

function LatestPlan({ jobId, scope }: { jobId: string; scope: (e: PlanEntry) => string }) {
  const run = useRun(jobId);
  return <section className={s.panel} aria-label='Latest run plan'>
    <Load q={run} rows={6}>{r => <>
      <SecHead title={`Plan of ${r.job_number}`}><span className={s.cap}>{r.progress ? `${r.progress.finished} of ${r.progress.planned} finished` : 'not planned yet'}</span></SecHead>
      {r.plan.length ? <PlanTable plan={r.plan} scopeLabel={scope} /> : <p className={s.cap}>The plan is made when a worker claims the job.</p>}
    </>}</Load>
  </section>;
}
