'use client';

/* The evidence tools. The preview is the preserved original served by the API (with HTTP range
   support for video and audio); metadata is NEX-MET's latest extraction (run by T-MIR in a worker); integrity
   re-hashes the stored bytes on the server; the custody timeline is the evidence's append-only event history;
   analysis shows every T-MIR module's state for this evidence (modules/analysis). */
import Link from 'next/link';
import { useState } from 'react';
import { ArrowRight, LoaderCircle, ShieldCheck, TriangleAlert } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import x from './evidence.module.css';
import { ApiError, api, type Evidence, type InvestigationEvent, type IntegrityVerification, type Metadata } from '@/api';
import { useIntegrity, useMetadata } from '@/api/hooks';
import { invalidate, prime, useQuery } from '@/api/query';
import { Dot, Empty, ErrorState, Hash, Load, PageHead, SecHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { bytes, duration, eventDetail, eventLabel, eventTone, mediaLabel, metadataLabel, methodLabel, sourceTypeLabel, toneColor, utc } from '@/utils/labels';
import { useLoadedEvidence } from './EvidenceShell';
import { EvidenceAnalysisSummary } from '@/modules/analysis/Analysis';
import { EvidenceViewer } from '@/modules/viewer/Viewer';

/* ── media viewer: the stored original, never a stand-in ── */
export function MediaViewer({ ev, compact }: { ev: Evidence; compact?: boolean }) {
  const src = api.evidence.previewUrl(ev.evidence_id);
  const [failed, setFailed] = useState(false);
  if (failed) return <div className={p.mediaFrame} style={compact ? { minHeight: 200 } : undefined}><p className={s.cap} style={{ padding: 24, textAlign: 'center' }}>This browser cannot display {ev.mime_type}, or the original could not be loaded. Use Download original to examine it locally.</p></div>;
  return <figure style={{ display: 'grid', gap: 8 }}>
    <div className={p.mediaFrame} style={compact ? { minHeight: 200, maxHeight: 420 } : undefined}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {ev.media_type === 'IMAGE' && <img src={src} alt={`Preserved original ${ev.filename}`} onError={() => setFailed(true)} />}
      {ev.media_type === 'VIDEO' && <video src={src} controls preload='metadata' onError={() => setFailed(true)} />}
      {ev.media_type === 'AUDIO' && <audio src={src} controls preload='metadata' onError={() => setFailed(true)} />}
    </div>
    <figcaption className={p.mediaNote}>The preserved original as stored (SHA-256 {ev.sha256.slice(0, 12)}…), displayed by your browser. Viewing it does not change it.</figcaption>
  </figure>;
}

/* ── /evidence/:id: the original first, the facts that matter beside it, the full acquisition record on request ── */
export function EvidenceOverview() {
  const ev = useLoadedEvidence();
  const md = useMetadata(ev.evidence_id);
  const integrity = useIntegrity(ev.evidence_id);
  const last = integrity.data?.last_verification;
  return <div className={`${s.page} ${x.ev}`}>
    <h1 className={s.srOnly}>{ev.evidence_number} overview: {ev.filename}</h1>
    <div className={x.hero}>
      <MediaViewer ev={ev} compact />
      <div className={p.stack}>
        <div className={x.facts} aria-label='Key facts'>
          <div className={x.fact}><span>Type</span><b>{mediaLabel[ev.media_type]} · {ev.detected_format}</b></div>
          <div className={x.fact}><span>Size</span><b>{bytes(ev.file_size)}</b></div>
          <div className={x.fact}><span>Received</span><b>{utc(ev.received_at)}</b></div>
          <div className={x.fact}><span>Integrity</span><b data-tone={last ? (last.result === 'MATCH' ? 'ok' : 'alert') : undefined}>{last ? (last.result === 'MATCH' ? 'Bytes match' : last.result === 'MISMATCH' ? 'BYTES DIFFER' : 'ORIGINAL MISSING') : 'Not re-verified yet'}</b></div>
        </div>
        <EvidenceAnalysisSummary ev={ev} />
        <section className={s.panel} aria-label='Metadata summary'>
          <SecHead title='Metadata'><Link href={paths.evidence(ev.evidence_id, 'metadata')} className={s.secLink}>All metadata <ArrowRight size={13} /></Link></SecHead>
          <Load q={md} rows={3} notFound={<p className={s.cap}>No metadata extraction is recorded for this evidence.</p>}>{m => <MetadataHighlights ev={ev} m={m} />}</Load>
        </section>
      </div>
    </div>
    <div className={p.stack} style={{ marginTop: 20 }}>
      <details className={x.disclose} aria-label='Acquisition record'>
        <summary>Acquisition and preservation<small>how it was obtained, by whom, when</small></summary>
        <dl className={s.kv}>
          <div><dt>Evidence</dt><dd className={s.mono}>{ev.evidence_number}</dd></div>
          <div><dt>File name (as supplied)</dt><dd style={{ overflowWrap: 'anywhere' }}>{ev.filename}</dd></div>
          <div><dt>Detected type</dt><dd>{mediaLabel[ev.media_type]} · {ev.detected_format} · {ev.mime_type}</dd></div>
          <div><dt>Type claimed by the uploader</dt><dd>{ev.declared_content_type ?? '—'}</dd></div>
          <div><dt>Size</dt><dd>{bytes(ev.file_size)} ({ev.file_size.toLocaleString()} bytes)</dd></div>
          <div><dt>Obtained as</dt><dd>{sourceTypeLabel[ev.source_type]} · {methodLabel[ev.acquisition_method]}</dd></div>
          <div><dt>Received</dt><dd>{utc(ev.received_at)}</dd></div>
          <div><dt>Preserved</dt><dd>{utc(ev.preserved_at)}</dd></div>
          <div><dt>Recorded by</dt><dd>{ev.acquired_by}</dd></div>
        </dl>
        {ev.description && <p className={p.notes}>{ev.description}</p>}
      </details>
      <details className={x.disclose} aria-label='Integrity'>
        <summary>SHA-256<small><Link href={paths.evidence(ev.evidence_id, 'integrity')} className={s.secLink}>Verify <ArrowRight size={13} /></Link></small></summary>
        <Hash value={ev.sha256} />
        <p className={s.cap}>Computed by the server from the received bytes. A matching hash proves the stored bytes are unchanged; it does not prove the content is authentic.</p>
      </details>
    </div>
  </div>;
}

function MetadataHighlights({ ev, m }: { ev: Evidence; m: Metadata }) {
  if (m.status !== 'EXTRACTED') return <p className={p.warnLine}><TriangleAlert size={15} />{metadataLabel[m.status]}{m.error ? `: ${m.error}` : ''}</p>;
  const sm = m.summary as Record<string, unknown>;
  const rows: [string, string][] = [];
  if (ev.media_type === 'IMAGE') {
    rows.push(['Dimensions', `${sm.width} × ${sm.height}`], ['Format', `${sm.format} · ${sm.mode}`], ['EXIF', sm.exif_present ? 'present' : 'none found']);
    const exif = (sm.exif ?? {}) as Record<string, unknown>;
    if (exif.Make || exif.Model) rows.push(['Device (claimed in EXIF)', [exif.Make, exif.Model].filter(Boolean).join(' ')]);
  } else {
    const c = (sm.container ?? {}) as Record<string, unknown>;
    const v = ((sm.video_streams ?? []) as Record<string, unknown>[])[0];
    const a = ((sm.audio_streams ?? []) as Record<string, unknown>[])[0];
    rows.push(['Container', String(c.format_name ?? '—')], ['Duration', duration(c.duration_seconds as number)]);
    if (v) rows.push(['Video', `${v.codec} · ${v.width} × ${v.height} · ${v.average_frame_rate ?? '—'} fps`]);
    if (a) rows.push(['Audio', `${a.codec} · ${a.sample_rate_hz} Hz · ${a.channels} ch`]);
    if (!a && ev.media_type === 'VIDEO') rows.push(['Audio', 'no audio stream']);
  }
  const ts = (sm.embedded_timestamps ?? {}) as Record<string, unknown>;
  if (Object.keys(ts).length) rows.push(['Embedded timestamp (unverified)', String(Object.values(ts)[0])]);
  return <dl className={s.kv}>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

/* ── /evidence/:id/preview ── */
export function EvidencePreview() {
  const ev = useLoadedEvidence();
  return <div className={s.page}>
    <PageHead title='Preview' desc='The preserved original, served byte-for-byte from protected storage. Video and audio stream with seeking.' />
    <MediaViewer ev={ev} />
  </div>;
}

/* ── /evidence/:id/metadata ── */
export function EvidenceMetadata() {
  const ev = useLoadedEvidence();
  const q = useMetadata(ev.evidence_id);
  return <div className={s.page}>
    <PageHead title='Metadata' desc='What the file says about itself. Metadata can be missing, wrong or edited, so none of it is treated as fact.' />
    <Load q={q} rows={6} notFound={<Empty title='No metadata recorded'>No extraction has been recorded for this evidence.</Empty>}>{m => <div className={`${p.grid2} ${x.ev}`}>
      <div className={p.stack}>
        {m.status !== 'EXTRACTED' && <p className={p.warnLine}><TriangleAlert size={15} />{metadataLabel[m.status]}{m.error ? `: ${m.error}` : ''}</p>}
        {Object.entries(m.summary).filter(([k]) => !['embedded_timestamps', 'embedded_timestamps_note', 'exif', 'gps'].includes(k)).map(([k, v]) => <MetaGroup key={k} name={k} value={v} />)}
        {['exif', 'gps'].filter(k => m.summary[k] && Object.keys(m.summary[k] as object).length).map(k => <MetaGroup key={k} name={k} value={m.summary[k]} />)}
        {m.raw && <details className={s.panel}><summary className={s.title} style={{ cursor: 'pointer' }}>Raw extractor output (FFprobe JSON)</summary><pre className={p.json}>{JSON.stringify(m.raw, null, 2)}</pre></details>}
      </div>
      <div className={p.stack}>
        <section className={s.panel} aria-label='Extraction record'>
          <SecHead title='Extraction record' />
          <dl className={s.kv}>
            <div><dt>Status</dt><dd><Dot tone={m.status === 'EXTRACTED' ? 'ok' : 'alert'}>{metadataLabel[m.status]}</Dot></dd></div>
            <div><dt>Extractor</dt><dd>{m.extractor}</dd></div>
            <div><dt>Version</dt><dd className={s.mono} style={{ fontSize: 12 }}>{m.extractor_version}</dd></div>
            <div><dt>Extracted</dt><dd>{utc(m.extracted_at)}</dd></div>
            <div><dt>Versions on record</dt><dd>{m.version_count}</dd></div>
          </dl>
          <div><p className={s.cap}>Input SHA-256 (the bytes the extractor read)</p><Hash value={m.input_sha256} label='input SHA-256' /></div>
        </section>
        <section className={s.panel} aria-label='Embedded timestamps'>
          <SecHead title='Timestamps inside the file' />
          {Object.keys((m.summary.embedded_timestamps ?? {}) as object).length ? <table className={p.metaTable}><tbody>{Object.entries(m.summary.embedded_timestamps as Record<string, unknown>).map(([k, v]) => <tr key={k}><th>{k}</th><td>{String(v)}</td></tr>)}</tbody></table> : <p className={s.cap}>None found.</p>}
          <p className={p.warnLine}><TriangleAlert size={14} />Claimed by the file, not verified. They are kept apart from NEXTRON’s own receipt time ({utc(ev.received_at)}).</p>
        </section>
      </div>
    </div>}</Load>
  </div>;
}

const titleOf = (k: string) => k.replace(/_/g, ' ').replace(/^\w/, ch => ch.toUpperCase());
const show = (v: unknown): string => v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v);

function MetaGroup({ name, value }: { name: string; value: unknown }) {
  if (Array.isArray(value)) {
    if (!value.length) return null;
    return <>{value.map((item, i) => <MetaGroup key={i} name={`${name.replace(/s$/, '')} ${i + 1}`} value={item} />)}</>;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    return <details className={x.disclose} aria-label={titleOf(name)} open={entries.length <= 8}>
      <summary>{titleOf(name)}<small>{entries.length} field{entries.length === 1 ? '' : 's'}</small></summary>
      <table className={p.metaTable}><tbody>{entries.map(([k, v]) => <tr key={k}><th>{k}</th><td>{show(v)}</td></tr>)}</tbody></table>
    </details>;
  }
  return <section className={s.panel}><table className={p.metaTable}><tbody><tr><th>{titleOf(name)}</th><td>{show(value)}</td></tr></tbody></table></section>;
}

/* ── /evidence/:id/integrity ── */
export function EvidenceIntegrity() {
  const ev = useLoadedEvidence();
  const { notify } = useWorkspace();
  const state = useIntegrity(ev.evidence_id);
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState<IntegrityVerification | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  async function verify() {
    setBusy(true); setErr(null);
    try {
      const r = await api.evidence.verify(ev.evidence_id);
      setFresh(r);
      if (state.data) prime(`ev:${ev.evidence_id}:integrity`, { ...state.data, last_verification: r });
      invalidate(`ev:${ev.evidence_id}`);
      notify(r.result === 'MATCH' ? 'Integrity verified: stored bytes match' : 'Integrity check FAILED', r.result === 'MATCH' ? 'ok' : 'alert');
    } catch (e) { setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }
  const last = fresh ?? state.data?.last_verification ?? null;
  return <div className={s.page}>
    <PageHead title='Integrity' desc='Recompute the SHA-256 of the stored original on the server and compare it with the digest recorded when it was preserved. Every check is recorded in the custody history.'>
      <button className={`${s.btn} ${s.primary}`} onClick={verify} disabled={busy}>{busy ? <><LoaderCircle size={15} className={s.spin} />Hashing stored bytes…</> : <><ShieldCheck size={15} />Verify integrity now</>}</button>
    </PageHead>
    {err && <ErrorState error={err} title='Verification did not run' />}
    <div className={`${x.verdict} ${x.ev}`} data-r={last?.result ?? 'NONE'} role='status' style={{ marginTop: err ? 16 : 0 }}>
      {last?.result === 'MATCH' ? <ShieldCheck size={26} /> : last ? <TriangleAlert size={26} /> : <ShieldCheck size={26} />}
      <div><b>{last ? (last.result === 'MATCH' ? 'The stored original is unchanged' : last.result === 'MISMATCH' ? 'The stored original has CHANGED since preservation' : 'The stored original is MISSING') : 'Not checked since preservation'}</b>
        <small>{last ? `Last checked ${utc(last.verified_at)}. A match proves the bytes are unchanged; it does not prove the content is authentic.` : 'Recompute the SHA-256 to confirm the stored bytes still match the digest recorded at preservation.'}</small></div>
      <span />
    </div>
    <div className={p.grid2}>
      <section className={s.panel} aria-label='Recorded digest'>
        <SecHead title='Recorded at preservation' />
        <Hash value={ev.sha256} />
        <dl className={s.kv}><div><dt>Algorithm</dt><dd>SHA-256</dd></div><div><dt>Size</dt><dd>{ev.file_size.toLocaleString()} bytes</dd></div><div><dt>Preserved</dt><dd>{utc(ev.preserved_at)}</dd></div><div><dt>Storage</dt><dd>Read-only original; never modified by NEXTRON</dd></div></dl>
      </section>
      <section className={s.panel} aria-label='Latest verification' aria-live='polite'>
        <SecHead title='Latest verification' />
        <Load q={state} rows={2}>{() => last ? <>
          <p className={p.verdict} data-r={last.result}>{last.result === 'MATCH' ? <ShieldCheck size={18} /> : <TriangleAlert size={18} />}{last.result === 'MATCH' ? 'Stored bytes match the recorded SHA-256' : last.result === 'MISMATCH' ? 'Stored bytes DO NOT match the recorded SHA-256' : 'The stored original is MISSING'}</p>
          <dl className={s.kv}>
            <div><dt>Checked</dt><dd>{utc(last.verified_at)}</dd></div>
            <div><dt>Computed SHA-256</dt><dd className={s.mono} style={{ fontSize: 12 }}>{last.computed_sha256 ?? '—'}</dd></div>
            <div><dt>Computed size</dt><dd>{last.computed_size?.toLocaleString() ?? '—'} bytes</dd></div>
          </dl>
          <p className={s.cap}>{last.note}</p>
        </> : <p className={s.cap}>Not re-verified since preservation. Run a check to confirm the stored bytes are unchanged.</p>}</Load>
      </section>
    </div>
  </div>;
}

/* ── /evidence/:id/timeline ── */
export function EvidenceTimeline() {
  const ev = useLoadedEvidence();
  const q = useQuery(`ev:${ev.evidence_id}:history`, async () => {
    const all: InvestigationEvent[] = [];
    let after = 0;
    for (let i = 0; i < 20; i++) { const page = await api.evidence.history(ev.evidence_id, after, 200); all.push(...page.data); if (!page.cursor.has_more || page.cursor.next_after === null) break; after = page.cursor.next_after; }
    return all;
  });
  return <div className={s.page}>
    <PageHead title='Custody timeline' desc='Every recorded action on this evidence since it arrived, oldest first. The record is append-only: entries cannot be edited or deleted.' />
    <Load q={q} rows={5}>{events => events.length ? <div className={x.ev}>{[...new Set(events.map(e => e.occurred_at.slice(0, 10)))].map(day => <section key={day} aria-label={`Custody on ${day}`}>
      <p className={x.day}>{day}</p>
      <ol className={x.chain}>{events.filter(e => e.occurred_at.startsWith(day)).map(e => <li key={e.event_id} style={{ ['--c' as string]: toneColor[eventTone(e.event_type)] }}>
        <time>{e.occurred_at.slice(11, 19)} UTC</time>
        <div><b>{eventLabel(e.event_type)}</b><small>#{e.sequence} · {e.actor}{eventDetail(e.event_type, e.payload) ? ` · ${eventDetail(e.event_type, e.payload)}` : ''}</small></div>
      </li>)}</ol>
    </section>)}</div> : <Empty title='No custody events' />}</Load>
  </div>;
}

/* ── /evidence/:id/analysis ── */
export function EvidenceAnalysis() {
  return <div className={s.page} style={{ maxWidth: 'none' }}><EvidenceViewer ev={useLoadedEvidence()} /></div>;
}
