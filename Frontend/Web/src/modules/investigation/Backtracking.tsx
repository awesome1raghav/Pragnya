'use client';

import Link from 'next/link';
import { useState } from 'react';
import { api, ApiError, type BacktrackingComparison, type ReviewDecision } from '@/api';
import { useQuery, invalidate } from '@/api/query';
import { ErrorState, PageHead, SecHead } from '@/components/ui';
import { paths } from '@/config/routes';
import { useCaseId } from '@/modules/investigations/CaseShell';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import bt from './backtracking.module.css';

const decisions: ReviewDecision[] = ['ACCEPTED', 'REJECTED', 'INCONCLUSIVE', 'NEEDS_MORE_EVIDENCE'];

export default function Backtracking() {
  const caseId = useCaseId();
  const inventory = useQuery(`btk:${caseId}:candidates`, () => api.backtracking.candidates(caseId));
  const overview = useQuery(`btk:${caseId}:overview`, () => api.backtracking.overview(caseId), { refreshMs: 15000 });
  const history = useQuery(`btk:${caseId}:comparisons`, () => api.backtracking.comparisons(caseId), { refreshMs: 15000 });
  const sources = useQuery(`btk:${caseId}:sources`, () => api.backtracking.sources(caseId));
  const [seed, setSeed] = useState('');
  const [candidate, setCandidate] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useQuery(selected ? `btk:${caseId}:comparison:${selected}` : null,
    () => api.backtracking.comparison(caseId, selected!));
  const [decision, setDecision] = useState<ReviewDecision>('INCONCLUSIVE');
  const [rationale, setRationale] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const items = inventory.data?.candidates ?? [];
  const names = new Map(items.map(x => [x.evidence_id, x.display_number]));

  async function act(task: () => Promise<unknown>, success: string) {
    setBusy(true); setError(null); setMessage('');
    try { await task(); setMessage(success); invalidate(`btk:${caseId}`); }
    catch (e) { setError(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }

  return <div className={s.page}>
    <PageHead title='Backtracking' desc='Local candidate comparisons from preserved media. Shared content does not establish origin or direction.' />
    {error && <ErrorState error={error} />}{message && <p role='status' className={s.cap}>{message}</p>}
    <div className={p.grid2}>
      <section className={s.panel} aria-label='Local comparison controls'>
        <SecHead title='Compare preserved media' />
        <div className={bt.controls}>
          <label className={s.field}><span>Seed</span><select className={s.input} value={seed} onChange={e => setSeed(e.target.value)}><option value=''>Choose evidence</option>{items.map(x => <option key={x.evidence_id} value={x.evidence_id}>{x.display_number} · {x.filename}</option>)}</select></label>
          <label className={s.field}><span>Candidate</span><select className={s.input} value={candidate} onChange={e => setCandidate(e.target.value)}><option value=''>Choose evidence</option>{items.filter(x => x.evidence_id !== seed).map(x => <option key={x.evidence_id} value={x.evidence_id}>{x.display_number} · {x.filename}</option>)}</select></label>
        </div>
        <div className={bt.actions}>
          <button className={`${s.btn} ${s.primary}`} disabled={busy || !seed || !candidate || seed === candidate} onClick={() => act(() => api.backtracking.compare(caseId, seed, candidate), 'Verification saved')}>Verify pair</button>
          <button className={`${s.btn} ${s.ghost}`} disabled={busy || !seed || items.find(x => x.evidence_id === seed)?.media_type !== 'VIDEO'} onClick={() => act(() => api.backtracking.expand(caseId, seed), 'Bounded local expansion queued')}>Expand locally</button>
        </div>
        <p className={s.cap}>Expansion checks up to 100 local videos and 100 pairs. It follows candidate matches only.</p>
      </section>
      <section className={s.panel} aria-label='Search coverage'>
        <SecHead title='Coverage' />
        {overview.error ? <ErrorState error={overview.error} /> : overview.data ? <>
          <strong className={bt.metric}>{overview.data.coverage.pair_percent === null ? '—' : `${overview.data.coverage.pair_percent}%`}</strong>
          <p className={s.cap}>{overview.data.coverage.compared_pairs} of {overview.data.coverage.possible_video_pairs} video pairs compared · {overview.data.comparison_records} saved records.</p>
          {overview.data.truncated && <p className={s.cap}>Graph shows the latest {overview.data.shown_records} records.</p>}
        </> : <p className={s.cap}>Loading coverage…</p>}
      </section>
    </div>
    <section className={s.panel} aria-label='Candidate graph'>
      <SecHead title='Candidate graph' count={overview.data?.edges.length} />
      <p className={s.cap}>Each edge is a saved comparison. A review decision is shown separately.</p>
      {overview.data?.edges.length ? <ul className={bt.edges}>{overview.data.edges.map(edge => <li key={edge.comparison_id}>
        <button onClick={() => setSelected(edge.comparison_id)} className={bt.edge} aria-label={`Inspect comparison ${names.get(edge.from) ?? edge.from} to ${names.get(edge.to) ?? edge.to}`}>
          <span>{names.get(edge.from) ?? edge.from}</span><span aria-hidden='true'>↔</span><span>{names.get(edge.to) ?? edge.to}</span>
          <small>{edge.review_decision ?? 'Unreviewed'}</small>
        </button>
      </li>)}</ul> : <p className={s.cap}>No candidate edges yet.</p>}
    </section>
    <div className={p.grid2}>
      <section className={s.panel} aria-label='Comparison history'>
        <SecHead title='Comparison history' count={history.data?.comparisons.length} />
        {history.data?.comparisons.length ? <ul className={bt.history}>{history.data.comparisons.map(record => <li key={record.id}>
          <button onClick={() => setSelected(record.id)} aria-pressed={selected === record.id}>
            <b>{names.get(record.seed_evidence_id) ?? record.seed_evidence_id} ↔ {names.get(record.candidate_evidence_id) ?? record.candidate_evidence_id}</b>
            <small>{record.status.replaceAll('_', ' ')} · {record.current ? 'Current' : 'Superseded'} · {record.algorithm}</small>
          </button>
        </li>)}</ul> : <p className={s.cap}>No comparisons saved yet.</p>}
      </section>
      <section className={s.panel} aria-label='Evidence inspector'>
        <SecHead title='Evidence inspector' />
        {detail.data ? <Inspector record={detail.data} names={names} caseId={caseId} decision={decision} setDecision={setDecision}
          rationale={rationale} setRationale={setRationale} busy={busy} review={() => act(() => api.reviews.create(caseId, {
            subject_type: 'BACKTRACK_COMPARISON', subject_id: detail.data!.id, decision, rationale }), 'Review recorded')} />
          : detail.error ? <ErrorState error={detail.error} /> : <p className={s.cap}>Select an edge or comparison to inspect its measurements and review.</p>}
      </section>
    </div>
    <section className={s.panel} aria-label='Source occurrences'>
      <SecHead title='NEX-SRC occurrences' count={sources.data?.source_occurrences.length} />
      {sources.data?.source_occurrences.length ? <ul className={bt.sources}>{sources.data.source_occurrences.map(x => <li key={x.observation_id ?? x.source_id}>
        <b>{x.source_number} · revision {x.revision}</b><span>{x.outcome} · {x.backtracking_access.replaceAll('_', ' ')}</span>
        {x.preserved_evidence_id && <Link href={paths.evidence(x.preserved_evidence_id)}>{names.get(x.preserved_evidence_id) ?? 'Preserved evidence'}</Link>}
        <small>{x.url}</small>
      </li>)}</ul> : <p className={s.cap}>No source occurrences recorded for this case.</p>}
    </section>
  </div>;
}

function Inspector({ record, names, caseId, decision, setDecision, rationale, setRationale, busy, review }: {
  record: BacktrackingComparison; names: Map<string, string>; caseId: string; decision: ReviewDecision;
  setDecision: (d: ReviewDecision) => void; rationale: string; setRationale: (s: string) => void; busy: boolean; review: () => void;
}) {
  return <div className={bt.inspector}>
    <p><Link href={paths.evidence(record.seed_evidence_id)}>{names.get(record.seed_evidence_id) ?? 'Seed evidence'}</Link> ↔ <Link href={paths.evidence(record.candidate_evidence_id)}>{names.get(record.candidate_evidence_id) ?? 'Candidate evidence'}</Link></p>
    <p className={s.cap}>{record.status.replaceAll('_', ' ')} · {record.current ? 'Current inputs' : 'Outdated inputs or algorithm'} · {record.algorithm}</p>
    <dl><dt>Seed SHA-256</dt><dd>{record.seed_sha256}</dd><dt>Candidate SHA-256</dt><dd>{record.candidate_sha256}</dd>
      <dt>Seed coverage</dt><dd>{record.submitted_coverage_percent == null ? 'Unavailable' : `${record.submitted_coverage_percent}%`}</dd>
      <dt>Candidate coverage</dt><dd>{record.candidate_coverage_percent == null ? 'Unavailable' : `${record.candidate_coverage_percent}%`}</dd></dl>
    {record.checks && Object.entries(record.checks).map(([kind, check]) => <details key={kind}><summary>{kind} · {String(check.status ?? '')}</summary><pre>{JSON.stringify(check, null, 2)}</pre></details>)}
    {record.frame_pairs?.length ? <details><summary>Matched frame pairs ({record.frame_pairs.length})</summary><pre>{JSON.stringify(record.frame_pairs, null, 2)}</pre></details> : null}
    <p className={s.cap}>{record.limitations?.join(' · ')}</p>
    {record.review && <p className={s.cap}>Latest review: {record.review.decision} by {record.review.reviewer}. {record.review.rationale}</p>}
    <label className={s.field}><span>Review decision</span><select className={s.input} value={decision} onChange={e => setDecision(e.target.value as ReviewDecision)}>{decisions.map(x => <option key={x} value={x}>{x.replaceAll('_', ' ')}</option>)}</select></label>
    <label className={s.field}><span>Rationale</span><textarea className={s.input} value={rationale} onChange={e => setRationale(e.target.value)} maxLength={4000} /></label>
    <button className={`${s.btn} ${s.primary}`} disabled={busy || rationale.trim().length < 3} onClick={review}>Record review</button>
  </div>;
}
