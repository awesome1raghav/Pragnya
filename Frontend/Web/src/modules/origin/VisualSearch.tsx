'use client';

import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, API_BASE } from '@/api';
import { safeHttpUrl, visualSearch, type Crop, type VisualSearchMatch, type VisualSearchMode, type VisualSearchResult, type VisualSearchStatus } from '@/api/visualSearch';
import { SecHead } from '@/components/ui';
import { bytes } from '@/utils/labels';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';

function parseCrop(value: string): Crop | null {
  try {
    const c = JSON.parse(value);
    return Array.isArray(c) && c.length === 4 && c.every(n => Number.isSafeInteger(n) && n >= 0)
      && c[2] > c[0] && c[3] > c[1] ? c as Crop : null;
  } catch { return null; }
}

// A case change remounts the form, clearing files, consent and pending work together.
export default function VisualSearch({ caseId }: { caseId: string | null }) {
  return <SearchForm key={caseId ?? 'unscoped'} caseId={caseId} />;
}

function SearchForm({ caseId }: { caseId: string | null }) {
  const hintId = useId();
  const [status, setStatus] = useState<VisualSearchStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [mode, setMode] = useState<VisualSearchMode>('local');
  const [inputType, setInputType] = useState('file');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [topK, setTopK] = useState('10');
  const [cropText, setCropText] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisualSearchResult | null>(null);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    visualSearch.status(controller.signal).then(value => {
      if (!controller.signal.aborted) setStatus(value);
    }).catch(e => {
      if (!controller.signal.aborted) setStatusError(e instanceof ApiError ? e.message : 'Visual search status could not be read.');
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => () => pending.current?.abort(), []);

  const clear = () => {
    pending.current?.abort(); pending.current = null;
    setBusy(false); setError(null); setResult(null);
  };
  const changeQuery = () => { clear(); setConsent(false); };
  const crop = cropText.trim() ? parseCrop(cropText) : undefined;
  const unavailable = checking ? 'Checking visual search availability…'
    : statusError ? `Visual search unavailable: ${statusError}`
    : !status ? 'Visual search status is unavailable.'
    : mode === 'local' ? !status.local?.configured ? 'Local visual search is not configured.'
      : !status.local.model_ready ? 'The local visual search model is not ready.'
      : !status.local.reachable ? 'The local image index is unreachable.' : null
    : !status.web?.configured ? 'SerpApi web search is not configured.' : null;
  const invalid = !caseId ? 'Choose an investigation above to search.'
    : inputType === 'file' && !file ? 'Choose an image or screenshot.'
    : inputType === 'file' && (!file.type.startsWith('image/') || file.size === 0) ? 'Choose a non-empty image file.'
    : inputType === 'file' && status && file.size > status.max_bytes ? `The image exceeds the ${bytes(status.max_bytes)} limit.`
    : inputType === 'url' && !safeHttpUrl(url.trim()) ? 'Enter an HTTP(S) image URL without embedded credentials.'
    : !Number.isInteger(Number(topK)) || Number(topK) < 1 || Number(topK) > 50 ? 'Top K must be a whole number from 1 to 50.'
    : crop === null ? 'Crop must be [left,top,right,bottom] in whole pixels, with right > left and bottom > top.'
    : mode === 'web' && !consent ? 'Consent is required to send a search copy to SerpApi and Google Lens.' : null;
  const reason = unavailable ?? invalid;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (reason || busy) return;
    clear();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    try {
      const value = await visualSearch.search(caseId, {
        ...(inputType === 'file' ? { file } : { url: url.trim() }),
        mode, top_k: Number(topK), allow_external: mode === 'web' && consent, crop,
      }, controller.signal);
      if (!controller.signal.aborted) {
        if (value.scope !== (mode === 'local' ? 'case' : 'web') || !Array.isArray(value.matches) || !Array.isArray(value.limitations)) {
          throw new Error('Invalid search response');
        }
        setResult(value);
      }
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : 'Visual search could not be completed.');
    } finally {
      if (!controller.signal.aborted) { pending.current = null; setBusy(false); }
    }
  };

  return <section className={s.panel} aria-label='Visual search'>
    <SecHead title='Visual search' />
    <p className={s.cap}>Local search checks only indexed images in the selected investigation. Results are candidates; no sources are imported automatically.</p>
    <form className={p.form} onSubmit={submit} style={{ marginTop: 16 }}>
      <div className={p.formGrid}>
        <label className={s.field}><span>Search in</span><select className={s.input} value={mode} onChange={e => { changeQuery(); setMode(e.target.value as VisualSearchMode); }}>
          <option value='local'>Local · this investigation</option><option value='web' disabled={!status?.web?.configured}>Web · Google Lens via SerpApi{status?.web?.configured ? '' : ' (unavailable)'}</option>
        </select></label>
        <label className={s.field}><span>Top K (maximum results)</span><input className={s.input} type='number' min={1} max={50} step={1} required value={topK} onChange={e => { clear(); setTopK(e.target.value); }} /></label>
      </div>
      <label className={s.field}><span>Image input</span><select className={s.input} value={inputType} onChange={e => { changeQuery(); setInputType(e.target.value); setFile(null); setUrl(''); setCropText(''); }}>
        <option value='file'>Upload image or screenshot</option><option value='url'>Image URL</option>
      </select></label>
      {/* separate keys: a file input is uncontrolled and the URL input controlled, so React must not reuse one element for both */}
      {inputType === 'file' ? <label key='query-file' className={s.field}><span>Image or screenshot</span>
        <input className={s.input} type='file' accept='image/*' onChange={e => { changeQuery(); setFile(e.target.files?.[0] ?? null); setCropText(''); }} />
        {status && <small className={p.fieldHint}>Maximum {bytes(status.max_bytes)} per image.</small>}
      </label> : <label key='query-url' className={s.field}><span>Image URL</span>
        <input className={s.input} type='url' value={url} placeholder='https://example.org/image.jpg' onChange={e => { changeQuery(); setUrl(e.target.value); }} />
        <small className={p.fieldHint}>The NEXTRON server retrieves this image.</small>
      </label>}
      <details><summary className={s.cap}>Optional crop</summary>
        <label className={s.field} style={{ marginTop: 8 }}><span>Crop [left,top,right,bottom] in pixels</span>
          <input className={s.input} value={cropText} placeholder='[0,0,640,480]' onChange={e => { changeQuery(); setCropText(e.target.value); }} />
        </label>
      </details>
      {mode === 'web' && <label className={s.check}><input type='checkbox' checked={consent} onChange={e => { clear(); setConsent(e.target.checked); }} />
        <span>I consent to sending a derived search copy to SerpApi and Google Lens. NEXTRON also fetches public result previews.</span>
      </label>}
      <div className={p.formFoot}>
        <button className={`${s.btn} ${s.primary}`} disabled={busy || !!reason} aria-describedby={hintId}>{busy ? 'Searching…' : 'Search images'}</button>
        <button className={s.btn} type='button' disabled={checking || busy} onClick={() => { clear(); setStatus(null); setStatusError(null); setChecking(true); setRefresh(n => n + 1); }}>Check availability</button>
      </div>
      <p id={hintId} className={s.cap} role='status'>{busy ? 'Searching with the selected image…' : reason ?? (mode === 'local' ? 'Ready to search indexed case images.' : 'Ready to send a search copy to SerpApi and Google Lens.')}</p>
      {error && <p className={p.fieldError} role='alert'>{error}</p>}
    </form>
    {result && <div aria-label='Visual search results' role='region' style={{ marginTop: 16 }}>
      <p className={s.cap} role='status'>{result.matches.length} matches · {result.provider} · {result.scope === 'case' ? 'Selected investigation' : 'Web'}</p>
      <p className={s.cap} style={{ overflowWrap: 'anywhere' }}>Query SHA-256: <span className={s.mono}>{result.query_sha256}</span></p>
      {!result.matches.length && <p className={s.cap}>No matches found. This does not establish that the image is unique.</p>}
      <ul className={p.jobList}>{result.matches.map((match, i) => <Match key={i} match={match} local={mode === 'local' && result.scope === 'case'} />)}</ul>
      {result.limitations.length > 0 && <div role='note'><b>Limitations</b><ul>{result.limitations.map((text, i) => <li className={s.cap} key={i}>{text}</li>)}</ul></div>}
      {result.scope === 'web' && <p className={s.cap}>Preview images are fetched by NEXTRON from public sites. Opening a result visits the external site.</p>}
    </div>}
  </section>;
}

function Match({ match, local }: { match: VisualSearchMatch; local: boolean }) {
  const pageUrl = safeHttpUrl(match.page_url);
  const imageUrl = safeHttpUrl(match.image_url);
  // Never hotlink a remote image, even if it appears in a case-scoped response.
  const preview = local ? localPreview(match) : null;
  const webPreview = !local && match.thumbnail_token
    ? safeHttpUrl(`${API_BASE}/visual-search/thumbnails/${encodeURIComponent(match.thumbnail_token)}`) : null;
  return <li className={p.jobRow}>
    <div>
      <b style={{ overflowWrap: 'anywhere' }}>{match.title || match.evidence_id || 'Image match'}</b>
      <small>{match.match_type} · {match.score == null ? 'Score not supplied' : `${match.score}${match.score_kind ? ` · ${match.score_kind}` : ' · score type not supplied'}`}</small>
      {pageUrl && <a href={pageUrl} target='_blank' rel='noopener noreferrer' referrerPolicy='no-referrer' style={{ overflowWrap: 'anywhere' }}>Open page: {pageUrl}</a>}
      {imageUrl && <a href={imageUrl} target='_blank' rel='noopener noreferrer' referrerPolicy='no-referrer' style={{ overflowWrap: 'anywhere' }}>Open image: {imageUrl}</a>}
      {preview && <LocalPreview key={preview} src={preview} />}
      {webPreview && <WebPreview src={webPreview} />}
    </div>
  </li>;
}

function WebPreview({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? <small>Web preview unavailable; use the source link.</small>
    : <img src={src} alt='Web visual match preview' width={240} height={160} loading='lazy'
        referrerPolicy='no-referrer' style={{ objectFit: 'contain', maxWidth: '100%' }} onError={() => setFailed(true)} />;
}

function localPreview(match: VisualSearchMatch): string | null {
  if (match.evidence_id) return safeHttpUrl(api.evidence.previewUrl(match.evidence_id));
  try {
    const base = new URL(API_BASE, window.location.origin);
    const candidate = new URL(match.image_url, `${base.href}/`);
    return candidate.origin === base.origin && candidate.pathname.startsWith(`${base.pathname}/`) ? safeHttpUrl(candidate.href) : null;
  } catch { return null; }
}

function LocalPreview({ src }: { src: string }) {
  const [image, setImage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | undefined;
    // Fetch directly from the API without cookies or following redirects to external hosts.
    fetch(src, { credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error', signal: controller.signal })
      .then(async response => {
        if (!response.ok || !response.headers.get('content-type')?.startsWith('image/')) throw new Error('No image preview');
        const blob = await response.blob();
        if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setImage(objectUrl); }
      }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [src]);
  return failed ? <small>Image preview unavailable.</small> : image
    ? <img src={image} alt='Indexed case image' width={160} height={100} style={{ objectFit: 'contain', maxWidth: '100%' }} onError={() => setFailed(true)} />
    : <small>Loading case image…</small>;
}
