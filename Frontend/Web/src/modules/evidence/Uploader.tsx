'use client';

/* Evidence intake (NEX-CAP → NEX-EVD → NEX-MET). Files upload one at a time with real byte progress.
   The server's SHA-256 is the record; this browser also hashes files up to 256 MB and compares, which
   catches a corrupted transfer. Nothing is marked preserved until the API says it is. */
import Link from 'next/link';
import { useRef, useState } from 'react';
import { Check, LoaderCircle, Upload, X } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import x from './evidence.module.css';
import { ACQUISITION_METHODS, ApiError, SOURCE_TYPES, api, type AcquisitionMethod, type SourceType, type UploadedEvidence } from '@/api';
import { useStorageStatus } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { paths } from '@/config/routes';
import { bytes, mediaLabel, methodLabel, sourceTypeLabel } from '@/utils/labels';

const BROWSER_HASH_LIMIT = 256 * 1024 * 1024;
type Item = { key: string; file: File; state: 'waiting' | 'hashing' | 'uploading' | 'done' | 'error'; progress: number; localSha?: string; result?: UploadedEvidence; error?: ApiError };

async function sha256(file: File) {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export default function Uploader({ caseId, onDone }: { caseId: string; onDone?: (results: UploadedEvidence[]) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [over, setOver] = useState(false);
  const [sourceType, setSourceType] = useState<SourceType>('USER_UPLOAD');
  const [method, setMethod] = useState<AcquisitionMethod>('DIRECT_UPLOAD');
  const [description, setDescription] = useState('');
  const [running, setRunning] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const storage = useStorageStatus();

  const patch = (key: string, v: Partial<Item>) => setItems(list => list.map(i => i.key === key ? { ...i, ...v } : i));
  const add = (files: FileList | null) => {
    if (!files?.length) return;
    // copy now: the FileList is live, and the input is cleared right after this call, before React may run the updater
    const picked = [...files];
    setItems(list => [...list, ...picked.map(file => ({ key: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`, file, state: 'waiting' as const, progress: 0 }))]);
  };

  async function start() {
    setRunning(true);
    const done: UploadedEvidence[] = [];
    for (const item of items.filter(i => i.state === 'waiting' || i.state === 'error')) {
      let localSha: string | undefined;
      if (item.file.size <= BROWSER_HASH_LIMIT) {
        patch(item.key, { state: 'hashing', error: undefined });
        try { localSha = await sha256(item.file); } catch { localSha = undefined; }
      }
      patch(item.key, { state: 'uploading', progress: 0, localSha });
      abort.current = new AbortController();
      try {
        const result = await api.evidence.upload(caseId, item.file, { source_type: sourceType, acquisition_method: method, description: description.trim() || undefined }, prog => patch(item.key, { progress: prog }), abort.current.signal);
        patch(item.key, { state: 'done', progress: 1, result });
        done.push(result);
      } catch (e) {
        patch(item.key, { state: 'error', error: e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e)) });
      }
    }
    abort.current = null;
    setRunning(false);
    if (done.length) { invalidate('evidence', 'cases', `case:${caseId}`); onDone?.(done); }
  }

  const pending = items.filter(i => i.state === 'waiting' || i.state === 'error').length;
  return <div className={`${s.intake} ${x.ev}`}>
    <div className={s.side}>
      <label className={`${s.drop} ${over ? s.dropOver : ''}`} onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}>
        <Upload size={30} /><b>Drop original images, video or audio</b>
        <small>JPEG, PNG, GIF, WebP, BMP, TIFF · MP4, MOV, WebM, MKV, AVI · WAV, MP3, FLAC, OGG, AAC, M4A</small>
        <input type='file' multiple accept='image/*,video/*,audio/*' onChange={e => { add(e.target.files); e.target.value = ''; }} aria-label='Choose evidence files' disabled={running} />
        <span className={s.dropActions}><span className={`${s.btn} ${s.primary}`} aria-hidden='true'>Choose files</span></span>
        <small className={s.dropNext}>Preserved read-only with a server-side SHA-256, then analysed by a worker.</small>
      </label>
      <details className={x.disclose}><summary>What happens to each file<small>intake, preservation, analysis</small></summary>
        <ol className={s.cap} style={{ paddingLeft: 18, display: 'grid', gap: 4 }}>
          <li>This browser hashes files up to 256 MB, to compare with the server.</li>
          <li>The server streams the file into storage, computes its SHA-256 and checks it really is the media it claims to be.</li>
          <li>The original is kept read-only; nothing in NEXTRON ever changes it.</li>
          <li>Its analysis run is queued for a worker; results arrive live.</li>
        </ol>
      </details>
      {items.length > 0 && <section className={s.panel} aria-label='Upload queue'>
        <p className={s.title}>Files <span className={s.muted} style={{ fontWeight: 400 }}>{items.length}</span></p>
        <ul className={p.queue}>{items.map(i => <li key={i.key} className={p.qItem} data-s={i.state}>
          <b title={i.file.name}>{i.file.name}</b>
          <span className={s.cap}>{i.state === 'uploading' ? `${Math.round(i.progress * 100)}%` : i.state === 'hashing' ? 'hashing…' : bytes(i.file.size)}
            {(i.state === 'waiting' || i.state === 'error') && !running && <button className={s.iconBtn} style={{ width: 26, height: 26, display: 'inline-grid', marginLeft: 4 }} onClick={() => setItems(l => l.filter(x => x.key !== i.key))} aria-label={`Remove ${i.file.name}`}><X size={13} /></button>}
          </span>
          {i.state === 'uploading' && <i className={s.bar}><em style={{ transform: `scaleX(${i.progress})` }} /></i>}
          <small>{describe(i)}</small>
        </li>)}</ul>
      </section>}
    </div>

    <div className={s.side}>
      <section className={s.panel}>
        <p className={s.title}>Acquisition record</p>
        <label className={s.field}><span>How the evidence was obtained</span><select className={s.input} value={sourceType} onChange={e => setSourceType(e.target.value as SourceType)}>{SOURCE_TYPES.map(t => <option key={t} value={t}>{sourceTypeLabel[t]}</option>)}</select></label>
        <label className={s.field}><span>Acquisition method</span><select className={s.input} value={method} onChange={e => setMethod(e.target.value as AcquisitionMethod)}>{ACQUISITION_METHODS.map(m => <option key={m} value={m}>{methodLabel[m]}</option>)}</select></label>
        <label className={s.field}><span>Description <span className={s.muted}>(optional, applies to each file)</span></span><textarea className={`${s.input} ${p.textarea}`} maxLength={2000} value={description} onChange={e => setDescription(e.target.value)} placeholder='Where it came from, who supplied it, anything an investigator should know' /></label>
        <dl className={s.kv}><div><dt>Upload limit</dt><dd>{storage.data ? `${bytes(storage.data.max_upload_bytes)} per file` : storage.error ? 'unknown (storage status unavailable)' : '…'}</dd></div><div><dt>Original</dt><dd>Stored read-only, never modified</dd></div><div><dt>Recorded by</dt><dd>Local operator</dd></div></dl>
        <div className={p.formFoot}>
          <button className={`${s.btn} ${s.primary}`} onClick={start} disabled={running || pending === 0}>{running ? <><LoaderCircle size={15} className={s.spin} />Preserving…</> : <><Check size={15} />Upload and preserve {pending > 0 ? pending : ''} file{pending === 1 ? '' : 's'}</>}</button>
          {running && <button className={`${s.btn} ${s.ghost}`} onClick={() => abort.current?.abort()}>Cancel current upload</button>}
        </div>
      </section>
    </div>
  </div>;
}

function describe(i: Item) {
  if (i.state === 'waiting') return 'Waiting to upload';
  if (i.state === 'hashing') return 'Computing SHA-256 in this browser for comparison';
  if (i.state === 'uploading') return i.localSha ? `Browser SHA-256 ${i.localSha.slice(0, 16)}… · uploading` : 'Uploading (too large to hash in the browser)';
  if (i.state === 'error' && i.error) return `${i.error.message}${i.error.code ? ` (${i.error.code})` : ''}`;
  const r = i.result!;
  const match = i.localSha ? (i.localSha === r.sha256 ? 'matches the hash computed in this browser' : 'DIFFERS from the hash computed in this browser — the transfer may be corrupted') : 'not compared (file too large to hash in the browser)';
  return <>Preserved as <Link href={paths.evidence(r.evidence_id)} style={{ textDecoration: 'underline' }}>{r.evidence_number}</Link> · {mediaLabel[r.media_type]} {r.detected_format} · server SHA-256 {r.sha256.slice(0, 16)}… {match}{r.analysis_job ? <> · analysis <Link href={paths.evidence(r.evidence_id, 'analysis')} style={{ textDecoration: 'underline' }}>{r.analysis_job.job_number}</Link> queued</> : ''}{r.duplicates_in_case.length ? ` · identical bytes already in this case as ${r.duplicates_in_case.map(d => d.evidence_number).join(', ')}` : ''}</>;
}
