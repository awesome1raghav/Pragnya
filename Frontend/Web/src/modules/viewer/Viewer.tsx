'use client';

/* NEXTRON Universal Forensic Evidence Viewer: one examination workspace for every media type.
     Level 1  the summary line: what ran, what the methods inferred, what is located, what failed
     Level 2  findings, grouped (examination, relationships, case record) and filterable
     Level 3  the canvas for this media (image, video, audio) or its metadata and provenance, with the artifacts
     Level 4  the inspector: method, measurement, threshold and its source, limitations, artifacts with SHA-256,
              execution and result identifiers; below, the full execution record
   Selecting a finding focuses what it recorded (a region, a time range) and opens its details. Everything shown comes
   from GET /evidence/{id}/analysis, the evidence preview, its metadata and stored artifacts. */
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Download, Focus, PanelLeft, PanelRight, Play, Search, X } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { api, ApiError, type Evidence, type EvidenceAnalysis } from '@/api';
import { useEvidenceAnalysis, useMetadata } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { Dot, Empty, Load } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { FAMILY_LABEL, LEVEL, measurementRows, normalize, where, type Family, type ViewerFinding } from './normalize';
import { ImageCanvas } from './ImageCanvas';
import { VideoCanvas } from './VideoCanvas';
import { AudioCanvas } from './AudioCanvas';
import { MetaCanvas } from './MetaCanvas';
import { ExecutionRecord } from './ExecutionRecord';
import v from './viewer.module.css';

type Filter = 'all' | 'INFERENCE' | 'located';

export function EvidenceViewer({ ev }: { ev: Evidence }) {
  const q = useEvidenceAnalysis(ev.evidence_id);
  return <Load q={q} rows={6}>{a => <Workspace ev={ev} a={a} />}</Load>;
}

function Workspace({ ev, a }: { ev: Evidence; a: EvidenceAnalysis }) {
  const router = useRouter();
  const params = useSearchParams();
  const md = useMetadata(ev.evidence_id).data;
  const findings = useMemo(() => normalize(a), [a]);
  const [filter, setFilter] = useState<Filter>('all');
  const [text, setText] = useState('');
  const [tab, setTab] = useState<'media' | 'meta'>('media');
  const [panels, setPanels] = useState({ list: true, inspector: true });
  const [focus, setFocus] = useState(false);
  const selectedId = params.get('finding');
  const selected = findings.find(f => f.id === selectedId) ?? null;
  const select = (id: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (id) next.set('finding', id); else next.delete('finding');
    router.replace(`?${next.toString()}`, { scroll: false });
    const f = findings.find(x => x.id === id);
    if (f && (f.moduleId === 'NEX-MET' || f.moduleId === 'NEX-PRV')) setTab('meta'); else if (f && f.location.kind !== 'none') setTab('media');
    if (id) setPanels(p => ({ ...p, inspector: true }));
  };

  const needle = text.trim().toLowerCase();
  const shown = findings.filter(f => (filter === 'all' || (filter === 'located' ? f.location.kind !== 'none' : f.level === filter))
    && (!needle || `${f.title} ${f.moduleId} ${f.type} ${f.description ?? ''}`.toLowerCase().includes(needle)));
  const families = (['EXAMINATION', 'RELATIONSHIP', 'RECORD'] as Family[]).map(fam => [fam, shown.filter(f => f.family === fam)] as const).filter(([, xs]) => xs.length);

  const ran = a.modules.filter(m => m.latest);
  const failed = ran.filter(m => m.latest && m.latest.state === 'FAILED');
  const inferences = findings.filter(f => f.level === 'INFERENCE').length;
  const located = findings.filter(f => f.location.kind !== 'none').length;
  const running = a.latest_job && ['QUEUED', 'RUNNING'].includes(a.latest_job.state);

  useEffect(() => {  // keyboard: j/k move through findings, f toggles focus mode, Escape leaves it
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select') || e.metaKey || e.ctrlKey) return;
      const i = shown.findIndex(f => f.id === selectedId);
      if (e.key === 'j' && shown.length) select(shown[Math.min(shown.length - 1, i + 1)].id);
      else if (e.key === 'k' && shown.length) select(shown[Math.max(0, i - 1)].id);
      else if (e.key === 'f') setFocus(x => !x);
      else if (e.key === 'Escape') { if (focus) setFocus(false); else if (selectedId) select(null); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  const heatmaps = a.artifacts.filter(x => x.kind === 'HEATMAP' && x.mime_type === 'image/png' && x.attributes.method !== 'SPECTROGRAM');
  const sheet = a.artifacts.find(x => x.kind === 'FRAME_SET') ?? null;
  const track = a.artifacts.find(x => x.kind === 'AUDIO_TRACK') ?? null;
  const spectrogram = a.artifacts.find(x => x.kind === 'HEATMAP' && x.attributes.method === 'SPECTROGRAM') ?? null;
  const frameRate = useMemo(() => {
    const vs = (md?.summary?.video_streams as { frame_rate?: string | number; avg_frame_rate?: string }[] | undefined)?.[0];
    const raw = vs?.frame_rate ?? vs?.avg_frame_rate;
    if (typeof raw === 'number') return raw > 0 ? raw : null;
    if (typeof raw === 'string' && raw.includes('/')) { const [n, d] = raw.split('/').map(Number); return d ? n / d : null; }
    return raw ? Number(raw) || null : null;
  }, [md]);

  const canvas = tab === 'meta' ? <MetaCanvas md={md} findings={findings} />
    : ev.media_type === 'IMAGE' ? <ImageCanvas evidenceId={ev.evidence_id} filename={ev.filename} findings={findings} selected={selected} onSelect={select} heatmaps={heatmaps} />
    : ev.media_type === 'VIDEO' ? <VideoCanvas evidenceId={ev.evidence_id} findings={findings} selected={selected} onSelect={select} sheet={sheet} frameRate={frameRate} />
    : <AudioCanvas evidenceId={ev.evidence_id} findings={findings} selected={selected} onSelect={select} track={track} spectrogram={spectrogram} />;

  return <div className={v.viewer} data-focus={focus || undefined}>
    <h1 className={v.srOnly}>Analysis of {ev.evidence_number}: {ev.filename}</h1>
    <div className={v.summary} aria-label='Examination summary'>
      <p>{a.latest_job ? <><b>{ran.length}</b> module{ran.length === 1 ? '' : 's'} ran · <b>{inferences}</b> inference{inferences === 1 ? '' : 's'} · <b>{located}</b> located finding{located === 1 ? '' : 's'}{failed.length ? <> · <b className={v.bad}>{failed.length} failed</b></> : null}</>
        : 'Not analysed yet.'}{running ? <span className={v.running}> · analysis running</span> : null}</p>
      <div className={v.summaryActions}>
        <RunButton ev={ev} running={!!running} />
        <button className={v.iconBtn} aria-pressed={panels.list} onClick={() => setPanels(p => ({ ...p, list: !p.list }))} aria-label='Findings panel'><PanelLeft size={16} /></button>
        <button className={v.iconBtn} aria-pressed={panels.inspector} onClick={() => setPanels(p => ({ ...p, inspector: !p.inspector }))} aria-label='Inspector panel'><PanelRight size={16} /></button>
        <button className={v.iconBtn} aria-pressed={focus} onClick={() => setFocus(x => !x)} aria-label='Focus mode' title='Focus mode (f)'><Focus size={16} /></button>
      </div>
    </div>

    <div className={v.grid} data-list={panels.list && !focus || undefined} data-inspector={panels.inspector && !focus || undefined}>
      {panels.list && !focus && <section className={v.list} aria-label='Findings'>
        <div className={v.filters} role='group' aria-label='Show'>
          {([['all', `All ${findings.length}`], ['INFERENCE', `Inferences ${inferences}`], ['located', `Located ${located}`]] as [Filter, string][]).map(([k, label]) =>
            <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}</button>)}
        </div>
        {findings.length > 8 && <label className={v.find}><Search size={13} /><input value={text} onChange={e => setText(e.target.value)} placeholder='Search findings' aria-label='Search findings' /></label>}
        {families.length ? families.map(([fam, xs]) => <FamilyGroup key={fam} fam={fam} xs={xs} selectedId={selectedId} onSelect={select} />)
          : <Empty title={findings.length ? 'No finding matches' : 'No findings yet'}>{findings.length ? 'Change the filter or the search.' : running ? 'The analysis is running; findings appear as modules finish.' : 'Run the analysis to examine this evidence.'}</Empty>}
      </section>}

      <section className={v.canvas} aria-label='Examination canvas'>
        <div className={v.tabs} role='tablist' aria-label='Canvas'>
          <button role='tab' aria-selected={tab === 'media'} onClick={() => setTab('media')}>{ev.media_type === 'IMAGE' ? 'Image' : ev.media_type === 'VIDEO' ? 'Video' : 'Audio'}</button>
          <button role='tab' aria-selected={tab === 'meta'} onClick={() => setTab('meta')}>Metadata and provenance</button>
          {focus && <button className={v.leaveFocus} onClick={() => setFocus(false)}><X size={14} />Leave focus</button>}
        </div>
        {canvas}
      </section>

      <AnimatePresence initial={false}>{panels.inspector && !focus && <motion.aside key='inspector' className={v.inspector} aria-label='Finding details'
        initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
        {selected ? <Inspector f={selected} ev={ev} onClose={() => select(null)} /> : <div className={v.inspectorEmpty}>
          <b>Select a finding</b><p>Its method, measurement, threshold, limitations and supporting artifacts appear here, and the canvas moves to what it recorded.</p>
          <p className={v.hint}><kbd>j</kbd>/<kbd>k</kbd> next and previous · <kbd>f</kbd> focus mode</p>
        </div>}
      </motion.aside>}</AnimatePresence>
    </div>

    <ExecutionRecord a={a} ev={ev} />
  </div>;
}

function FamilyGroup({ fam, xs, selectedId, onSelect }: { fam: Family; xs: ViewerFinding[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(fam === 'EXAMINATION');
  const show = open || xs.some(x => x.id === selectedId);
  return <div className={v.family}>
    <button className={v.familyHead} onClick={() => setOpen(x => !x)} aria-expanded={show}><ChevronDown size={14} style={{ transform: show ? undefined : 'rotate(-90deg)' }} />{FAMILY_LABEL[fam]}<small>{xs.length}</small></button>
    {show && <ul>{xs.map(f => <li key={f.id}><button className={v.item} data-on={f.id === selectedId || undefined} data-level={f.level} onClick={() => onSelect(f.id)} aria-current={f.id === selectedId || undefined}>
      <span className={v.itemTitle}>{f.title}</span>
      <span className={v.itemMeta}><span data-level={f.level}>{LEVEL[f.level].label}</span> · {f.moduleId}{f.location.kind !== 'none' ? ` · ${f.location.kind === 'region' ? 'region' : 'time range'}` : ''}</span>
    </button></li>)}</ul>}
  </div>;
}

function Inspector({ f, ev, onClose }: { f: ViewerFinding; ev: Evidence; onClose: () => void }) {
  const loc = where(f.location);
  const rows = measurementRows(f.measurement);
  return <motion.div key={f.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .18 }} className={v.inspectorBody}>
    <header>
      <Dot tone={LEVEL[f.level].tone}>{LEVEL[f.level].label}</Dot>
      <button className={v.iconBtn} onClick={onClose} aria-label='Close details'><X size={15} /></button>
    </header>
    <h2>{f.title}</h2>
    <p className={v.meaning}>{LEVEL[f.level].meaning}</p>
    {f.description && <p>{f.description}</p>}
    <dl className={v.facts}>
      <div><dt>Method</dt><dd>{f.method}</dd></div>
      <div><dt>Where</dt><dd>{loc ?? (ev.media_type === 'IMAGE' && f.moduleId === 'NEX-IMG' ? 'Image-level only: this method records no pixel region, so none is drawn.' : 'Not localised: the finding applies to the item as a whole.')}</dd></div>
      {f.score !== null && <div><dt>Score</dt><dd className={v.mono}>{f.score} <small>({(f.scoreKind ?? '').toLowerCase().replace(/_/g, ' ')}: the method’s own measure, not a probability)</small></dd></div>}
      {f.threshold && <div><dt>Threshold</dt><dd className={v.mono}>{f.threshold.value}{f.threshold.above !== null && <small> · {f.threshold.above ? 'above' : 'below'}</small>}{f.threshold.source && <small> · source: {f.threshold.source}</small>}</dd></div>}
    </dl>
    {rows.length > 0 && <details className={v.more}><summary>Measurement ({rows.length})</summary><dl className={v.facts}>{rows.map(([k, x]) => <div key={k}><dt>{k}</dt><dd className={v.mono}>{x}</dd></div>)}</dl></details>}
    {f.limitations.length > 0 && <div className={v.limits}><b>What this cannot tell you</b><ul>{f.limitations.map(l => <li key={l}>{l}</li>)}</ul></div>}
    {f.artifacts.length > 0 && <div className={v.arts}><b>Supporting artifacts</b>{f.artifacts.map(x => <a key={x.artifact_id} href={api.analysis.artifactUrl(x.artifact_id)} target='_blank' rel='noreferrer' className={v.art}>
      {x.mime_type === 'image/png' && /* eslint-disable-next-line @next/next/no-img-element */ <img src={api.analysis.artifactUrl(x.artifact_id)} alt={`${f.moduleId} ${String(x.attributes.method ?? x.kind).toLowerCase()} artifact`} loading='lazy' />}
      <span>{String(x.attributes.method ?? x.kind).toLowerCase().replace(/_/g, ' ')}<small className={v.mono}>SHA-256 {x.sha256.slice(0, 16)}…</small></span><Download size={14} />
    </a>)}</div>}
    <details className={v.more}><summary>Traceability</summary><dl className={v.facts}>
      <div><dt>Module</dt><dd>{f.moduleId} · {f.moduleName}{f.moduleVersion ? ` · ${f.moduleVersion}` : ''}</dd></div>
      {Object.keys(f.toolVersions).length > 0 && <div><dt>Tools</dt><dd className={v.mono}>{Object.entries(f.toolVersions).map(([k, x]) => `${k} ${x}`).join(' · ')}</dd></div>}
      <div><dt>Result</dt><dd><a href={`${api.analysis.resultUrl(f.resultId)}`} target='_blank' rel='noreferrer' className={v.mono}>{f.resultId}</a></dd></div>
      <div><dt>Execution</dt><dd className={v.mono}>{f.executionId ?? 'case-level module: see the run plan'}</dd></div>
      <div><dt>Finding</dt><dd className={v.mono}>{f.id}</dd></div>
      <div><dt>Recorded</dt><dd className={v.mono}>{f.createdAt.slice(0, 19).replace('T', ' ')} UTC</dd></div>
    </dl></details>
    <p className={v.hint}>Record a decision about this finding on the investigation’s <Link href={paths.caseReview(ev.case_id)} className={v.link}>Review</Link> tab.</p>
  </motion.div>;
}

function RunButton({ ev, running }: { ev: Evidence; running: boolean }) {
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { const job = await api.analysis.analyze(ev.evidence_id); notify(`Queued ${job.job_number}`); invalidate('jobs', `ev:${ev.evidence_id}`); }
    catch (e) { notify(e instanceof ApiError ? e.message : 'The run could not be queued', 'alert'); }
    finally { setBusy(false); }
  };
  return <button className={`${s.btn} ${s.sm} ${s.primary}`} onClick={go} disabled={busy || running}><Play size={13} />{running ? 'Run in progress' : busy ? 'Queuing…' : 'Run analysis'}</button>;
}

