'use client';

/* Intake: every stage shown here really runs on the file you give it.
   1 Read   — streams the file in 8 MB slices (progress is bytes read)
   2 Hash   — SHA-256 with Web Crypto over the bytes read (files over 512 MB are hashed on the first 512 MB, said so)
   3 Probe  — the browser's own decoder reports duration, size and resolution
   4 Frames — six frames are decoded and drawn at even intervals for the contact sheet
   5 Seal   — the evidence record is written (here: into the session) */
import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Check, FileVideo, LoaderCircle, ShieldCheck, Upload } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { mb } from '@/demo/utils/labels';
import { useData } from '@/demo/stores/workspace.store';
import { api } from '@/demo/api';
import { PageHead, fmt, type Ctx } from '@/demo/components/ui';

const CAP = 512 * 1048576, SLICE = 8 * 1048576;
type Stage = { label: string; state: 'wait' | 'run' | 'done' | 'skip'; note?: string; p?: number; ms?: number };
const fresh = (): Stage[] => ['Read file', 'Compute SHA-256', 'Probe media', 'Extract frames', 'Seal evidence record'].map(label => ({ label, state: 'wait' }));

export default function Intake({ go, notify, caseId: activeCase }: Ctx) {
  const { cases, addEvidence } = useData();
  const [upload, setUpload] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [stages, setStages] = useState<Stage[]>(fresh());
  const [hash, setHash] = useState('');
  const [probe, setProbe] = useState<{ kind: string; w: number; h: number; d: number } | null>(null);
  const [frames, setFrames] = useState<{ src: string; t: number }[]>([]);
  const [over, setOver] = useState(false);
  const [caseId, setCaseId] = useState(activeCase);
  const [sealed, setSealed] = useState(false);
  const [pick, setPick] = useState(0);
  const busy = stages.some(x => x.state === 'run');
  const token = useRef(0);

  const upd = (i: number, v: Partial<Stage>) => setStages(st => st.map((x, j) => j === i ? { ...x, ...v } : x));

  async function processFile(f: File) {
    const my = ++token.current; const alive = () => token.current === my;
    setFile(f); setStages(fresh()); setHash(''); setProbe(null); setFrames([]); setSealed(false); setPick(0);
    // 1 · read in slices
    let t0 = performance.now(); upd(0, { state: 'run', p: 0 });
    const limit = Math.min(f.size, CAP), parts: Uint8Array[] = [];
    for (let at = 0; at < limit; at += SLICE) {
      parts.push(new Uint8Array(await f.slice(at, Math.min(limit, at + SLICE)).arrayBuffer()));
      if (!alive()) return; upd(0, { p: Math.min(1, (at + SLICE) / limit) });
    }
    upd(0, { state: 'done', p: 1, ms: performance.now() - t0, note: `${mb(limit)} read${f.size > CAP ? ` of ${mb(f.size)}` : ''}` });
    // 2 · hash
    t0 = performance.now(); upd(1, { state: 'run' });
    const buf = new Uint8Array(limit); let o = 0; for (const p of parts) { buf.set(p, o); o += p.length; }
    const digest = await crypto.subtle.digest('SHA-256', buf); if (!alive()) return;
    const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
    setHash(hex); upd(1, { state: 'done', ms: performance.now() - t0, note: f.size > CAP ? 'Hashed on the first 512 MB' : 'Whole file' });
    // 3 · probe with the browser's decoder
    t0 = performance.now(); upd(2, { state: 'run' });
    const url = URL.createObjectURL(f);
    const isVideo = f.type.startsWith('video/'), isImage = f.type.startsWith('image/');
    let el: HTMLVideoElement | HTMLImageElement | null = null;
    try {
      if (isVideo) {
        const v = document.createElement('video'); v.muted = true; v.preload = 'auto'; v.src = url;
        await new Promise<void>((res, rej) => { v.onloadedmetadata = () => res(); v.onerror = () => rej(new Error('decode')); });
        el = v; setProbe({ kind: 'Video', w: v.videoWidth, h: v.videoHeight, d: v.duration });
      } else if (isImage) {
        const im = new window.Image(); im.src = url; await im.decode(); el = im; setProbe({ kind: 'Image', w: im.naturalWidth, h: im.naturalHeight, d: 0 });
      }
      upd(2, { state: el ? 'done' : 'skip', ms: performance.now() - t0, note: el ? undefined : 'Not a format this browser can decode' });
    } catch { upd(2, { state: 'skip', note: 'This browser cannot decode the file; the hash still stands' }); }
    if (!alive()) return;
    // 4 · frames
    t0 = performance.now(); upd(3, { state: el ? 'run' : 'skip', p: 0 });
    if (el) {
      const cv = document.createElement('canvas'), ctx = cv.getContext('2d')!;
      const W = 320, H = Math.round(W * ((el instanceof HTMLVideoElement ? el.videoHeight : el.naturalHeight) || 9) / ((el instanceof HTMLVideoElement ? el.videoWidth : el.naturalWidth) || 16));
      cv.width = W; cv.height = H; const out: { src: string; t: number }[] = [];
      for (let i = 0; i < 6; i++) {
        if (el instanceof HTMLVideoElement) {
          const at = (el.duration || 1) * (i + .5) / 6; el.currentTime = at;
          await new Promise<void>(res => { (el as HTMLVideoElement).onseeked = () => res(); });
          ctx.drawImage(el, 0, 0, W, H); out.push({ src: cv.toDataURL('image/jpeg', .72), t: at });
        } else {
          const im = el, cw = im.naturalWidth / 2, ch = im.naturalHeight / 2; // six crops across the still
          ctx.drawImage(im, (i % 3) * cw / 2, Math.floor(i / 3) * ch, cw, ch, 0, 0, W, H); out.push({ src: cv.toDataURL('image/jpeg', .72), t: 0 });
        }
        if (!alive()) return; setFrames([...out]); upd(3, { p: (i + 1) / 6 });
      }
      upd(3, { state: 'done', p: 1, ms: performance.now() - t0, note: '6 frames decoded' });
    }
    URL.revokeObjectURL(url);
    upd(4, { state: 'wait', note: 'Ready to seal' });
  }

  const take = (f?: File | null) => { if (f) processFile(f); };
  const sample = async () => { const r = await fetch('/images/evidence/rain-street-1280.webp'); const b = await r.blob(); processFile(new File([b], 'street_cam_sample.webp', { type: b.type || 'image/webp' })); };
  const ready = stages[3].state === 'done' || stages[3].state === 'skip';

  return <div className={s.page}>
    <PageHead title='Scan evidence' desc='Drop the original file. It is read, hashed and probed in your browser before anyone works on a copy; every number below comes from the file itself.' />
    <div className={s.intake}>
      <div className={s.side}>
        {!file ? <label className={`${s.drop} ${over ? s.dropOver : ''}`} onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); take(e.dataTransfer.files[0]); }}>
          <Upload size={30} /><b>Drop the original video or image</b><small>MP4, MOV, WebM, JPEG or PNG</small>
          <input type='file' accept='video/*,image/*' onChange={e => take(e.target.files?.[0])} aria-label='Choose evidence file' />
          <span className={s.dropActions}>
            <span className={`${s.btn} ${s.primary}`} aria-hidden='true'>Choose file</span>
            <button type='button' className={`${s.btn} ${s.ghost}`} onClick={e => { e.preventDefault(); sample(); }}>Try a sample still</button>
          </span>
          <small className={s.dropNext}>Next, it is read and hashed in this browser, probed, and six frames are pulled for review. Nothing is uploaded until you seal it.</small>
        </label> : <section className={s.panel}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <FileVideo size={22} style={{ color: 'var(--gold)', flex: 'none' }} />
            <div style={{ minWidth: 0, flex: 1 }}><b className={s.title} style={{ overflowWrap: 'anywhere' }}>{file.name}</b><p className={s.cap}>{mb(file.size)} · {file.type || 'unknown type'}{probe && ` · ${probe.w} × ${probe.h}`}{probe?.d ? ` · ${fmt(probe.d)}` : ''}</p></div>
            <button className={`${s.btn} ${s.sm}`} onClick={() => { token.current++; setFile(null); setStages(fresh()); }} disabled={busy}>Replace</button>
          </div>
          {hash && <div><p className={s.cap}>SHA-256</p><code className={s.hash}>{hash}</code></div>}
        </section>}
        {frames.length > 0 && <section className={s.panel}>
          <p className={s.title}>Contact sheet <span className={s.muted} style={{ fontWeight: 400 }}>decoded from the file</span></p>
          <figure className={s.sheetBig}><img src={frames[Math.min(pick, frames.length - 1)].src} alt={`Frame ${pick + 1} of ${frames.length}`} /><figcaption>{frames[Math.min(pick, frames.length - 1)].t ? fmt(frames[Math.min(pick, frames.length - 1)].t) : `Crop ${pick + 1}`} · {pick + 1} of {frames.length}</figcaption></figure>
          <div className={s.sheet} role='group' aria-label='Frames'>{frames.map((f, i) => <motion.button key={i} aria-pressed={pick === i} onClick={() => setPick(i)} aria-label={`Show frame ${i + 1}`} initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .25 }}><img src={f.src} alt='' /></motion.button>)}</div>
        </section>}
      </div>

      <div className={s.side}>
        {file && <section className={s.panel} style={{ padding: 8 }}>
          <p className={s.title} style={{ padding: '8px 12px 0' }}>Processing</p>
          <ol className={s.pipeline}>{stages.map((st, i) => <li key={st.label} className={s.pStep} data-s={st.state === 'skip' ? 'done' : st.state}>
            <span>{st.state === 'done' ? <Check size={14} /> : st.state === 'run' ? <LoaderCircle size={14} className={s.spin} /> : i + 1}</span>
            <div><b>{st.label}</b>{st.note && <p>{st.note}</p>}{st.state === 'run' && st.p !== undefined && <i className={s.bar}><em style={{ transform: `scaleX(${st.p})` }} /></i>}</div>
            <time>{st.ms !== undefined ? `${Math.round(st.ms)} ms` : ''}</time>
          </li>)}</ol>
        </section>}
        <section className={s.panel}>
          <label className={s.field}><span>Attach to investigation</span><select className={s.input} value={caseId} onChange={e => setCaseId(e.target.value)}>{cases.map(c => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}</select></label>
          <dl className={s.kv}><div><dt>Retention</dt><dd>5 years</dd></div><div><dt>Preservation</dt><dd>Bit-for-bit, read-only</dd></div><div><dt>Access</dt><dd>Case team</dd></div></dl>
          {!sealed ? <button className={`${s.btn} ${file && ready && hash ? s.primary : ''}`} disabled={!file || !ready || !hash || upload !== null} onClick={async () => {
            upd(4, { state: 'run', p: 0, note: 'Uploading the original' }); setUpload(0);
            try { const rec = await api.uploadEvidence({ caseId, file: file!, sha256: hash }, p => { setUpload(p); upd(4, { p }); }); addEvidence(rec); upd(4, { state: 'done', note: `Sealed as ${rec.id} in ${caseId}` }); setSealed(true); notify(`Sealed ${file!.name} as ${rec.id}`); }
            catch (e) { upd(4, { state: 'wait', note: `Upload failed: ${e instanceof Error ? e.message : e}` }); }
            setUpload(null);
          }}><ShieldCheck size={15} />{!file ? 'Waiting for a file' : !ready ? 'Processing…' : upload !== null ? `Uploading ${Math.round(upload * 100)}%` : 'Seal evidence record'}</button>
            : <button className={`${s.btn} ${s.primary}`} onClick={() => go('investigate', { caseId, run: true })}>Analyze in workspace <ArrowRight size={15} /></button>}
        </section>
      </div>
    </div>
  </div>;
}
