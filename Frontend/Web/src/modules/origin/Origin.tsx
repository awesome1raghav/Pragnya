'use client';

/* /sources and /lineage (plan Step 5).
   Sources: URLs an investigator added, retrieved by a worker under the SSRF rules. Each source opens into an
   inspection that keeps apart what was submitted, what NEXTRON observed (retrieval time, address hops, hashes, the
   evidence it preserved), what the source claims (title, publication time: unverified), and what stopped retrieval.
   Lineage: NEX-MOC's candidate relationships between versions of media in one investigation. Every relationship is a
   candidate, never an established derivation; similarity is a fingerprint measure, not a probability; "earlier
   observed" rests on publication times sources claim. The pages say so where the claim is made. */
import Link from 'next/link';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, ChevronDown, Plus, RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import o from './origin.module.css';
import { api, ApiError, type Lineage, type LineageEdge, type Source, type SourceState } from '@/api';
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
const host = (u: string) => { try { return new URL(u).host; } catch { return u; } };

/* ── /sources ── */
export function SourcesPage() {
  const { caseId } = useCaseContext();
  const q = useSources(caseId);
  return <div className={s.page}>
    <PageHead title='Sources' desc='Where a piece of media was published, as far as public, permitted sources show it. NEXTRON retrieves each URL itself and records every attempt.' />
    <CaseScope />
    <div className={o.layout}>
      <div className={p.stack}>
        {caseId ? <AddSource caseId={caseId} /> : <section className={s.panel}><p className={s.cap}>Choose an investigation above to add a source to it.</p></section>}
        <section className={s.panel} aria-label='Sources list'>
          <SecHead title='Sources' count={q.data?.pagination.total_items} />
          <Load q={q} rows={3}>{r => r.data.length ? <ul className={o.sources}>{r.data.map((src, i) => <SourceRow key={src.source_id} src={src} i={i} />)}</ul>
            : <Empty title='No sources yet'>Add the URL where the media was posted. Retrieved media becomes evidence, with its own hash and custody record.</Empty>}</Load>
        </section>
      </div>
      <div className={p.stack}>
        <VisualSearch caseId={caseId} />
        <Connectors />
      </div>
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
    <form onSubmit={submit} className={o.addForm}>
      <input className={s.input} type='url' required value={url} onChange={e => setUrl(e.target.value)} placeholder='Public URL of the post or media' aria-label='Source URL' />
      <button className={`${s.btn} ${s.primary}`} disabled={busy || !url.trim()}><Plus size={15} />{busy ? 'Adding…' : 'Add'}</button>
    </form>
    {error && <p className={p.fieldError} role='alert'>{error}</p>}
    <p className={s.cap}>Internal and private addresses are never fetched. Platform posts (YouTube, X, Instagram, Facebook, TikTok) need an approved connector and are recorded as such.</p>
  </section>;
}

function SourceRow({ src, i }: { src: Source; i: number }) {
  const { notify } = useWorkspace();
  const [open, setOpen] = useState(false);
  const refresh = async () => {
    try { await api.sources.refresh(src.source_id); notify(`Retrieving ${src.source_number} again`); invalidate('sources', 'jobs'); }
    catch (e) { notify(e instanceof ApiError ? e.message : 'Refresh failed', 'alert'); }
  };
  return <motion.li className={o.source} data-open={open || undefined} aria-label={`${src.source_number} ${src.normalized_url}`}
    initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.03, duration: .2 }}>
    <div className={o.sourceHead}>
      <span className={o.sourceMain}>
        <b>{src.title ?? host(src.normalized_url)}</b>
        <small className={o.url}>{src.normalized_url}</small>
        <small><Dot tone={stateTone[src.state]}>{stateLabel[src.state]}</Dot>{src.state_detail ? ` · ${src.state_detail}` : ''}</small>
      </span>
      <span className={o.sourceActs}>
        <button className={`${s.btn} ${s.sm}`} onClick={() => setOpen(v => !v)} aria-expanded={open} aria-label={`History of ${src.source_number}`}><ChevronDown size={13} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform .2s' }} />Inspect</button>
        {src.state !== 'PENDING' && <button className={`${s.btn} ${s.sm}`} onClick={refresh} aria-label={`Retrieve ${src.source_number} again`}><RotateCcw size={13} />Refresh</button>}
      </span>
    </div>
    {open && <motion.div className={o.inspect} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} transition={{ duration: .22, ease: [.22, 1, .36, 1] }}>
      <div className={o.facets}>
        <dl className={o.facet}><dt>Submitted</dt>
          <dd><span className={s.mono}>{src.source_number}</span> · {src.created_by} · {utc(src.created_at)}</dd>
          <dd className={o.url}>{src.url}</dd>
          {src.url !== src.normalized_url && <dd className={o.url}>Normalised: {src.normalized_url}</dd>}</dl>
        <dl className={o.facet} data-kind='observed'><dt>Observed by NEXTRON</dt>
          <dd>{src.last_retrieved_at ? `Retrieved ${ago(src.last_retrieved_at)} (${utc(src.last_retrieved_at)})` : 'Not retrieved yet'} · revision {src.revision}</dd>
          <dd>{src.evidence_id ? <Link href={paths.evidence(src.evidence_id, 'analysis')} className={o.link}>Preserved as evidence: open in the viewer <ArrowRight size={12} /></Link> : 'No media was preserved from this source'}</dd></dl>
        <dl className={o.facet} data-kind='claimed'><dt>Claimed by the source <small>(not verified)</small></dt>
          <dd>Title: {src.title ?? 'none stated'}</dd>
          <dd>Publication time: {src.claimed_publication_time ?? 'none stated'}</dd></dl>
        {src.state !== 'RETRIEVED' && <dl className={o.facet} data-kind='limit'><dt>What stopped retrieval</dt><dd>{stateLabel[src.state]}{src.state_detail ? `: ${src.state_detail}` : ''}</dd></dl>}
      </div>
      <SourceHistory id={src.source_id} />
    </motion.div>}
  </motion.li>;
}

function SourceHistory({ id }: { id: string }) {
  const q = useSourceHistory(id);
  return <details className={o.history} open>
    <summary>Every retrieval attempt, with each address hop</summary>
    <Load q={q} rows={1}>{rows => rows.length ? <table className={p.planTable}>
      <thead><tr><th>Rev.</th><th>Outcome</th><th>Hops (address)</th><th>Received</th></tr></thead>
      <tbody>{rows.map(ob => <tr key={ob.revision}>
        <td>{ob.revision}<small>{utc(ob.retrieved_at)}</small></td>
        <td><Dot tone={stateTone[ob.outcome]}>{stateLabel[ob.outcome]}</Dot><small>{ob.detail}</small></td>
        <td>{ob.redirects.length ? ob.redirects.map((h, i) => <small key={i} style={{ overflowWrap: 'anywhere' }}>{h.status ?? '—'} {h.url} ({h.address ?? 'not resolved'})</small>) : <small>no request made</small>}</td>
        <td>{ob.content_type ?? '—'}<small>{bytes(ob.bytes_received)}{ob.media_sha256 ? ` · SHA-256 ${ob.media_sha256.slice(0, 12)}…` : ''}</small></td>
      </tr>)}</tbody>
    </table> : <p className={s.cap}>No retrieval has finished yet.</p>}</Load>
  </details>;
}

function Connectors() {
  const q = useConnectors();
  return <section className={s.panel} aria-label='Connectors'>
    <SecHead title='Connectors' />
    <Load q={q} rows={3}>{cs => <ul className={o.connectors}>{cs.map(c => <li key={c.connector} title={c.retrieves}>
      <span>{c.covers}</span><Dot tone={c.available ? 'ok' : 'mute'}>{c.available ? 'Available' : 'Not configured'}</Dot>
    </li>)}</ul>}</Load>
    <p className={s.cap}>Platform connectors need an approved API and credentials; none is configured, so those posts are recorded, not fetched.</p>
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
  const [sel, setSel] = useState<string | null>(l.edges[0]?.relationship_id ?? null);
  const byId = new Map(l.nodes.map(n => [n.evidence_id, n]));
  const name = (id: string) => byId.get(id)?.evidence_number ?? id.slice(0, 8);
  const edge = l.edges.find(e => e.relationship_id === sel) ?? null;
  if (!l.nodes.length) return <Empty title='No evidence yet'>Add evidence or sources to this investigation.</Empty>;
  return <div className={p.stack}>
    <p className={p.warnLine} role='note'>{l.note}</p>
    <div className={o.lineage}>
      <section className={s.panel} aria-label='Lineage graph'>
        <SecHead title='Graph' count={l.edges.length} />
        {l.edges.length ? <Graph l={l} sel={sel} onSel={setSel} /> : <p className={s.cap}>{l.nodes.some(n => n.fingerprinted) ? 'No two items in this investigation have similar fingerprints.' : 'Nothing has been fingerprinted yet; it happens in each evidence item’s analysis run.'}</p>}
        {l.edges.length > 0 && <p className={s.cap}>Dashed: no stated publication time orders the pair. Arrow: the source-claimed earlier item points to the later one. Select a line or a row for its basis.</p>}
      </section>
      {edge ? <Basis e={edge} name={name} /> : <section className={s.panel}><p className={s.cap}>Select a relationship to see what it rests on.</p></section>}
    </div>
    <section className={s.panel} aria-label='Candidate relationships'>
      <SecHead title='Candidate relationships' />
      {l.edges.length ? <div className={p.planWrap}><table className={p.planTable}>
        <thead><tr><th>Between</th><th>Relationship</th><th>Similarity</th><th>Earlier observed</th></tr></thead>
        <tbody>{l.edges.map(e => <tr key={e.relationship_id} data-on={sel === e.relationship_id || undefined} className={o.relRow} onClick={() => setSel(e.relationship_id)}>
          <td><Link href={paths.evidence(e.evidence_a, 'analysis')}>{name(e.evidence_a)}</Link> ↔ <Link href={paths.evidence(e.evidence_b, 'analysis')}>{name(e.evidence_b)}</Link></td>
          <td>{kindLabel[e.kind] ?? e.kind}<small>candidate · {String(e.basis.method ?? '')}</small></td>
          <td>{e.similarity.toFixed(2)}<small>{'phash_distance' in e.basis ? `pHash distance ${e.basis.phash_distance}` : 'bit_error_rate' in e.basis ? `bit error rate ${e.basis.bit_error_rate}` : ''}</small></td>
          <td>{e.earlier_observed ? name(e.earlier_observed) : '—'}<small>{e.ordering_basis ?? 'no stated publication times order them'}</small></td>
        </tr>)}</tbody>
      </table></div> : <p className={s.cap}>None.</p>}
    </section>
  </div>;
}

/** What one candidate relationship rests on, and what it does not establish. */
function Basis({ e, name }: { e: LineageEdge; name: (id: string) => string }) {
  const rows = Object.entries(e.basis).map(([k, v]) => [k.replace(/_/g, ' '), typeof v === 'object' ? JSON.stringify(v) : String(v)] as const);
  return <motion.section key={e.relationship_id} className={`${s.panel} ${o.basis}`} aria-label='Relationship basis' initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .2 }}>
    <SecHead title={<>{name(e.evidence_a)} ↔ {name(e.evidence_b)}</>}><Dot tone='gold'>Candidate</Dot></SecHead>
    <b className={o.basisKind}>{kindLabel[e.kind] ?? e.kind}</b>
    <p className={s.cap}>A candidate relationship: the fingerprints are close. It does not establish that one item was made from the other, or which came first.</p>
    <dl className={o.basisFacts}>
      <div><dt>Similarity</dt><dd className={s.mono}>{e.similarity.toFixed(3)} <small>fingerprint closeness from 0 to 1, not a probability of common origin</small></dd></div>
      <div><dt>Earlier observed</dt><dd>{e.earlier_observed ? `${name(e.earlier_observed)}: ${e.ordering_basis ?? ''}` : 'No stated publication times order them'}</dd></div>
      {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className={s.mono}>{v}</dd></div>)}
      <div><dt>Recorded</dt><dd className={s.mono}>{utc(e.created_at)}</dd></div>
    </dl>
    <div className={o.basisLinks}>
      <Link href={paths.evidence(e.evidence_a, 'analysis')} className={o.link}>Open {name(e.evidence_a)} <ArrowRight size={12} /></Link>
      <Link href={paths.evidence(e.evidence_b, 'analysis')} className={o.link}>Open {name(e.evidence_b)} <ArrowRight size={12} /></Link>
    </div>
  </motion.section>;
}

function Graph({ l, sel, onSel }: { l: Lineage; sel: string | null; onSel: (id: string) => void }) {
  const nodes = l.nodes.filter(n => l.edges.some(e => e.evidence_a === n.evidence_id || e.evidence_b === n.evidence_id));
  const r = nodes.length > 2 ? 120 : 110, cx = 200, cy = 160, R = 24;
  const pos = new Map(nodes.map((n, i) => [n.evidence_id, nodes.length === 2
    ? { x: cx + (i === 0 ? -r : r), y: cy }
    : { x: cx + r * Math.cos((2 * Math.PI * i) / nodes.length - Math.PI / 2), y: cy + r * Math.sin((2 * Math.PI * i) / nodes.length - Math.PI / 2) }]));
  const near = sel ? l.edges.find(e => e.relationship_id === sel) : null;
  return <svg viewBox='0 0 400 320' role='img' aria-label={`${nodes.length} evidence items, ${l.edges.length} candidate relationships`} className={o.graph}>
    <defs>
      <marker id='arrow' viewBox='0 0 10 10' refX='31' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='#e9a23b' /></marker>
      {nodes.map(n => <clipPath key={n.evidence_id} id={`clip-${n.evidence_id}`}><circle cx={pos.get(n.evidence_id)!.x} cy={pos.get(n.evidence_id)!.y} r={R} /></clipPath>)}
    </defs>
    {l.edges.map(e => {
      const a = pos.get(e.evidence_a)!, b = pos.get(e.evidence_b)!;
      const [from, to] = e.earlier_observed === e.evidence_b ? [b, a] : [a, b];
      const on = sel === e.relationship_id;
      return <g key={e.relationship_id} onClick={() => onSel(e.relationship_id)} style={{ cursor: 'pointer' }}>
        <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke='transparent' strokeWidth={14} />
        <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={on ? '#f0b85c' : e.earlier_observed ? '#e9a23b' : '#8d877c'} strokeWidth={(on ? 2 : 1) + 2 * e.similarity}
          strokeDasharray={e.earlier_observed ? undefined : '5 4'} markerEnd={e.earlier_observed ? 'url(#arrow)' : undefined} opacity={!sel || on ? 1 : 0.35} style={{ transition: 'opacity .2s' }} />
        <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8} textAnchor='middle' fontSize={11} fill={on ? '#f0b85c' : '#8d877c'}>{e.similarity.toFixed(2)}</text>
      </g>;
    })}
    {nodes.map(n => {
      const { x, y } = pos.get(n.evidence_id)!;
      const dim = near && near.evidence_a !== n.evidence_id && near.evidence_b !== n.evidence_id;
      return <a key={n.evidence_id} href={paths.evidence(n.evidence_id, 'analysis')} aria-label={`${n.evidence_number} ${n.filename}`} style={{ opacity: dim ? 0.4 : 1 }}>
        <circle cx={x} cy={y} r={R + 2} fill='#1c1a17' stroke={n.source_type === 'SOURCE_RETRIEVAL' ? '#7fa6bf' : '#bdb6aa'} strokeWidth={2} />
        {/* the evidence item itself, as preserved; other media show their type */}
        {n.media_type === 'IMAGE' ? <image href={api.evidence.previewUrl(n.evidence_id)} x={x - R} y={y - R} width={R * 2} height={R * 2} preserveAspectRatio='xMidYMid slice' clipPath={`url(#clip-${n.evidence_id})`} />
          : <text x={x} y={y + 4} textAnchor='middle' fontSize={11} fill='#8d877c'>{n.media_type.toLowerCase()}</text>}
        <text x={x} y={y + R + 18} textAnchor='middle' fontSize={12} fill='#bdb6aa'>{n.evidence_number}</text>
      </a>;
    })}
  </svg>;
}
