'use client';

/* /sources and /lineage (plan Step 5). Sources: URLs an investigator added, retrieved by a worker under the
   SSRF rules, each attempt recorded (hops, resolved addresses, outcome). Lineage: NEX-MOC's candidate relationships
   between versions of media in one investigation. Everything is a candidate; "earlier observed" rests on the
   publication times sources claim, and the pages say so. */
import Link from 'next/link';
import { useState } from 'react';
import { ChevronDown, Plus, RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, ApiError, type Lineage, type Source, type SourceState } from '@/api';
import { useConnectors, useLineage, useSourceHistory, useSources } from '@/api/hooks';
import { invalidate } from '@/api/query';
import CaseScope from '@/components/CaseScope';
import { Dot, Empty, Load, PageHead, SecHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';
import { ago, bytes, utc, type Tone } from '@/utils/labels';
import VisualSearch from './VisualSearch';

const stateTone: Record<SourceState, Tone> = {
  PENDING: 'steel', RETRIEVED: 'ok', METADATA_ONLY: 'gold', UNAVAILABLE: 'mute', RESTRICTED: 'gold', NOT_FOUND: 'mute',
  UNSUPPORTED: 'mute', RATE_LIMITED: 'gold', BLOCKED: 'alert', FAILED: 'alert',
};
const stateLabel: Record<SourceState, string> = {
  PENDING: 'Retrieving', RETRIEVED: 'Media retrieved', METADATA_ONLY: 'Metadata only', UNAVAILABLE: 'Unavailable', RESTRICTED: 'Access refused',
  NOT_FOUND: 'Not found', UNSUPPORTED: 'Needs a platform connector', RATE_LIMITED: 'Rate limited', BLOCKED: 'Blocked (internal address)', FAILED: 'Failed',
};

/* ── /sources ── */
export function SourcesPage() {
  const { caseId } = useCaseContext();
  const q = useSources(caseId);
  return <div className={s.page}>
    <PageHead title='Sources' desc='Where a piece of media was published, as far as public, permitted sources show it. NEXTRON retrieves each URL itself and records every attempt.' />
    <CaseScope />
    <div className={p.grid2}>
      <div className={p.stack}>
        {caseId ? <AddSource caseId={caseId} /> : <section className={s.panel}><p className={s.cap}>Choose an investigation above to add a source to it.</p></section>}
        <VisualSearch caseId={caseId} />
        <section className={s.panel} aria-label='Sources list'>
          <SecHead title='Sources' count={q.data?.pagination.total_items} />
          <Load q={q} rows={3}>{r => r.data.length ? <ul className={p.jobList}>{r.data.map(src => <SourceRow key={src.source_id} src={src} />)}</ul>
            : <Empty title='No sources yet'>Add the URL where the media was posted. Retrieved media becomes evidence, with its own hash and custody record.</Empty>}</Load>
        </section>
      </div>
      <Connectors />
    </div>
  </div>;
}

function AddSource({ caseId }: { caseId: string }) {
  const { notify } = useWorkspace();
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true); setError(null);
    try { const src = await api.sources.add(caseId, url); notify(`${src.source_number} added; retrieval queued`); setUrl(''); invalidate('sources', 'jobs'); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'The source could not be added'); }
    finally { setBusy(false); }
  };
  return <section className={s.panel} aria-label='Add a source'>
    <SecHead title='Add a source' />
    <form onSubmit={submit} className={p.form} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <label className={s.field} style={{ flex: 1, margin: 0 }}><span className={s.muted} style={{ fontSize: 12 }}>Public URL of the post or media</span>
        <input className={s.input} type='url' required value={url} onChange={e => setUrl(e.target.value)} placeholder='https://example.org/news/harbour-fire' aria-label='Source URL' />
      </label>
      <button className={`${s.btn} ${s.primary}`} disabled={busy || !url.trim()} style={{ marginTop: 22 }}><Plus size={15} />{busy ? 'Adding…' : 'Add'}</button>
    </form>
    {error && <p className={p.fieldError} role='alert'>{error}</p>}
    <p className={s.cap}>Internal and private addresses are never fetched. Platform posts (YouTube, X, Instagram, Facebook, TikTok) need an approved connector and are recorded as such.</p>
  </section>;
}

function SourceRow({ src }: { src: Source }) {
  const { notify } = useWorkspace();
  const [open, setOpen] = useState(false);
  const refresh = async () => {
    try { await api.sources.refresh(src.source_id); notify(`Retrieving ${src.source_number} again`); invalidate('sources', 'jobs'); }
    catch (e) { notify(e instanceof ApiError ? e.message : 'Refresh failed', 'alert'); }
  };
  return <li className={p.jobRow} aria-label={`${src.source_number} ${src.normalized_url}`}>
    <div>
      <b><span className={s.mono}>{src.source_number}</span> · {src.title ?? src.normalized_url}</b>
      <small style={{ overflowWrap: 'anywhere' }}>{src.normalized_url}</small>
      <small><Dot tone={stateTone[src.state]}>{stateLabel[src.state]}</Dot>{src.state_detail ? ` · ${src.state_detail}` : ''}</small>
      <small>{src.claimed_publication_time ? `Publication time claimed by the source: ${src.claimed_publication_time}` : 'No publication time stated'} · retrieved {src.last_retrieved_at ? ago(src.last_retrieved_at) : 'not yet'} · revision {src.revision}
        {src.evidence_id && <> · <Link href={paths.evidence(src.evidence_id)} style={{ textDecoration: 'underline' }}>evidence</Link></>}</small>
      {open && <SourceHistory id={src.source_id} />}
    </div>
    <div className={p.jobActs}>
      <button className={`${s.btn} ${s.sm}`} onClick={() => setOpen(v => !v)} aria-expanded={open} aria-label={`History of ${src.source_number}`}><ChevronDown size={13} style={{ transform: open ? 'rotate(180deg)' : undefined }} />History</button>
      {src.state !== 'PENDING' && <button className={`${s.btn} ${s.sm}`} onClick={refresh} aria-label={`Retrieve ${src.source_number} again`}><RotateCcw size={13} />Refresh</button>}
    </div>
  </li>;
}

function SourceHistory({ id }: { id: string }) {
  const q = useSourceHistory(id);
  return <Load q={q} rows={1}>{rows => rows.length ? <table className={p.planTable} style={{ marginTop: 8 }}>
    <thead><tr><th>Rev.</th><th>Outcome</th><th>Hops (address)</th><th>Received</th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.revision}>
      <td>{o.revision}<small>{utc(o.retrieved_at)}</small></td>
      <td><Dot tone={stateTone[o.outcome]}>{stateLabel[o.outcome]}</Dot><small>{o.detail}</small></td>
      <td>{o.redirects.length ? o.redirects.map((h, i) => <small key={i} style={{ overflowWrap: 'anywhere' }}>{h.status ?? '—'} {h.url} ({h.address ?? 'not resolved'})</small>) : <small>no request made</small>}</td>
      <td>{o.content_type ?? '—'}<small>{bytes(o.bytes_received)}{o.media_sha256 ? ` · SHA-256 ${o.media_sha256.slice(0, 12)}…` : ''}</small></td>
    </tr>)}</tbody>
  </table> : <p className={s.cap}>No retrieval has finished yet.</p>}</Load>;
}

function Connectors() {
  const q = useConnectors();
  return <section className={s.panel} aria-label='Connectors'>
    <SecHead title='Connectors' />
    <Load q={q} rows={3}>{cs => <dl className={s.kv}>{cs.map(c => <div key={c.connector}><dt>{c.covers}</dt><dd><Dot tone={c.available ? 'ok' : 'mute'}>{c.available ? 'Available' : 'Not configured'}</Dot><small style={{ display: 'block', color: 'var(--mute)' }}>{c.retrieves}</small></dd></div>)}</dl>}</Load>
  </section>;
}

/* ── /lineage ── */
const kindLabel: Record<string, string> = {
  NEAR_DUPLICATE: 'Near-duplicate', SAME_CONTENT_VARIANT: 'Same content, varied', FRAME_OF_VIDEO: 'Frame of video',
  SHARED_VIDEO_SEGMENT: 'Shared video segment', SHARED_AUDIO: 'Shared audio',
};

export function LineagePage() {
  const { caseId } = useCaseContext();
  const q = useLineage(caseId);
  return <div className={s.page}>
    <PageHead title='Lineage' desc='Candidate relationships between versions of a piece of media, from fingerprint similarity and the sources’ stated publication times.' />
    <CaseScope />
    {!caseId ? <section className={s.panel}><p className={s.cap}>Lineage is built per investigation. Choose one above.</p></section>
      : <Load q={q} rows={4}>{l => <LineageView l={l} />}</Load>}
  </div>;
}

function LineageView({ l }: { l: Lineage }) {
  const byId = new Map(l.nodes.map(n => [n.evidence_id, n]));
  const name = (id: string) => byId.get(id)?.evidence_number ?? id.slice(0, 8);
  if (!l.nodes.length) return <Empty title='No evidence yet'>Add evidence or sources to this investigation.</Empty>;
  return <div className={p.stack}>
    <p className={p.warnLine} role='note'>{l.note}</p>
    <section className={s.panel} aria-label='Lineage graph'>
      <SecHead title='Graph' count={l.edges.length} />
      {l.edges.length ? <Graph l={l} /> : <p className={s.cap}>{l.nodes.some(n => n.fingerprinted) ? 'No two items in this investigation have similar fingerprints.' : 'Nothing has been fingerprinted yet; it happens in each evidence item’s analysis run.'}</p>}
    </section>
    <section className={s.panel} aria-label='Candidate relationships'>
      <SecHead title='Candidate relationships' />
      {l.edges.length ? <div className={p.planWrap}><table className={p.planTable}>
        <thead><tr><th>Between</th><th>Relationship</th><th>Similarity</th><th>Earlier observed</th></tr></thead>
        <tbody>{l.edges.map(e => <tr key={e.relationship_id}>
          <td><Link href={paths.evidence(e.evidence_a, 'analysis')}>{name(e.evidence_a)}</Link> ↔ <Link href={paths.evidence(e.evidence_b, 'analysis')}>{name(e.evidence_b)}</Link></td>
          <td>{kindLabel[e.kind] ?? e.kind}<small>candidate · {String(e.basis.method ?? '')}</small></td>
          <td>{e.similarity.toFixed(2)}<small>{'phash_distance' in e.basis ? `pHash distance ${e.basis.phash_distance}` : 'bit_error_rate' in e.basis ? `bit error rate ${e.basis.bit_error_rate}` : ''}</small></td>
          <td>{e.earlier_observed ? name(e.earlier_observed) : '—'}<small>{e.ordering_basis ?? 'no stated publication times order them'}</small></td>
        </tr>)}</tbody>
      </table></div> : <p className={s.cap}>None.</p>}
    </section>
  </div>;
}

function Graph({ l }: { l: Lineage }) {
  const nodes = l.nodes.filter(n => l.edges.some(e => e.evidence_a === n.evidence_id || e.evidence_b === n.evidence_id));
  const r = 120, cx = 180, cy = 150;
  const pos = new Map(nodes.map((n, i) => [n.evidence_id, { x: cx + r * Math.cos((2 * Math.PI * i) / nodes.length - Math.PI / 2), y: cy + r * Math.sin((2 * Math.PI * i) / nodes.length - Math.PI / 2) }]));
  return <svg viewBox='0 0 360 300' role='img' aria-label={`${nodes.length} evidence items, ${l.edges.length} candidate relationships`} style={{ width: '100%', maxWidth: 520 }}>
    <defs><marker id='arrow' viewBox='0 0 10 10' refX='22' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='#e9a23b' /></marker></defs>
    {l.edges.map(e => {
      const a = pos.get(e.evidence_a)!, b = pos.get(e.evidence_b)!;
      const [from, to] = e.earlier_observed === e.evidence_b ? [b, a] : [a, b];
      return <line key={e.relationship_id} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={e.earlier_observed ? '#e9a23b' : '#8d877c'} strokeWidth={1 + 2 * e.similarity}
        strokeDasharray={e.earlier_observed ? undefined : '4 4'} markerEnd={e.earlier_observed ? 'url(#arrow)' : undefined} />;
    })}
    {nodes.map(n => { const { x, y } = pos.get(n.evidence_id)!; return <g key={n.evidence_id}>
      <circle cx={x} cy={y} r={16} fill='#1c1a17' stroke={n.source_type === 'SOURCE_RETRIEVAL' ? '#7fa6bf' : '#bdb6aa'} strokeWidth={2} />
      <text x={x} y={y + 30} textAnchor='middle' fontSize={12} fill='#bdb6aa'>{n.evidence_number}</text>
      <text x={x} y={y + 4} textAnchor='middle' fontSize={11} fill='#8d877c'>{n.media_type[0]}</text>
    </g>; })}
  </svg>;
}
