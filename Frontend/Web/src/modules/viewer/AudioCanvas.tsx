'use client';

/* Audio examination canvas. Playback is the preserved original. The waveform is computed here from the analysis' own
   16 kHz working copy (AUDIO_TRACK artifact) with the Web Audio decoder: the drawn shape is the signal, not an animation.
   The spectrogram is the stored artifact, laid on the same time axis using the duration it records. Highlighted
   intervals are exactly the time ranges findings recorded. Drag to select and loop a range. */
import { useEffect, useRef, useState } from 'react';
import { Pause, Play, Repeat } from 'lucide-react';
import { api, type Artifact } from '@/api';
import { fmtTime, type ViewerFinding } from './normalize';
import v from './viewer.module.css';

export function AudioCanvas({ evidenceId, findings, selected, onSelect, track, spectrogram }: {
  evidenceId: string; findings: ViewerFinding[]; selected: ViewerFinding | null; onSelect: (id: string) => void; track: Artifact | null; spectrogram: Artifact | null;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [peaks, setPeaks] = useState<Float32Array | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dur, setDur] = useState(Number(track?.attributes.duration_s ?? 0));
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [loop, setLoop] = useState(false);
  const drag = useRef<number | null>(null);
  const timed = findings.filter(f => f.location.kind === 'time');

  // decode the working copy once and reduce it to min/max pairs per pixel column
  useEffect(() => {
    if (!track) { setProblem('No working copy was stored for this audio, so the waveform cannot be drawn.'); return; }
    let cancelled = false;
    (async () => {
      try {
        const buf = await (await fetch(api.analysis.artifactUrl(track.artifact_id))).arrayBuffer();
        const ctx = new AudioContext();
        const decoded = await ctx.decodeAudioData(buf);
        void ctx.close();
        const data = decoded.getChannelData(0), cols = 1600, per = Math.max(1, Math.floor(data.length / cols)), out = new Float32Array(cols * 2);
        for (let c = 0; c < cols; c++) {
          let lo = 1, hi = -1;
          for (let i = c * per, end = Math.min(data.length, (c + 1) * per); i < end; i++) { const x = data[i]; if (x < lo) lo = x; if (x > hi) hi = x; }
          out[c * 2] = lo; out[c * 2 + 1] = hi;
        }
        if (!cancelled) { setPeaks(out); setDur(decoded.duration); }
      } catch { if (!cancelled) setProblem('The working copy could not be decoded in this browser; playback of the original still works.'); }
    })();
    return () => { cancelled = true; };
  }, [track]);

  useEffect(() => {
    const el = canvas.current; if (!el || !peaks) return;
    const dpr = window.devicePixelRatio || 1, w = el.clientWidth, h = el.clientHeight;
    el.width = w * dpr; el.height = h * dpr;
    const g = el.getContext('2d')!; g.scale(dpr, dpr); g.clearRect(0, 0, w, h);
    const cols = peaks.length / 2, mid = h / 2;
    g.fillStyle = '#bdb6aa';
    for (let x = 0; x < w; x++) {
      const c = Math.floor((x / w) * cols), lo = peaks[c * 2], hi = peaks[c * 2 + 1];
      g.fillRect(x, mid - hi * mid * 0.95, 1, Math.max(1, (hi - lo) * mid * 0.95));
    }
  }, [peaks]);

  useEffect(() => {
    if (selected?.location.kind !== 'time' || !audio.current) return;
    const { start, end } = selected.location;
    setRange([start, Math.max(end, start + 0.05)]); setLoop(true);
    audio.current.currentTime = start; void audio.current.play();
  }, [selected]);

  // keep the loop exact while playing (timeupdate is too coarse)
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      const el = audio.current; if (!el) return;
      if (loop && range && el.currentTime >= range[1]) el.currentTime = range[0];
      setT(el.currentTime); raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, loop, range]);

  const at = (clientX: number, el: HTMLElement) => { const r = el.getBoundingClientRect(); return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * dur; };
  const toggle = () => { const el = audio.current; if (!el) return; if (el.paused) { if (loop && range && (el.currentTime < range[0] || el.currentTime > range[1])) el.currentTime = range[0]; void el.play(); } else el.pause(); };
  const pct = (s: number) => `${dur ? (s / dur) * 100 : 0}%`;

  return <div className={v.canvasWrap}>
    <audio ref={audio} src={api.evidence.previewUrl(evidenceId)} preload='metadata' onLoadedMetadata={e => { if (!dur) setDur(e.currentTarget.duration); }}
      onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onTimeUpdate={e => setT(e.currentTarget.currentTime)} />
    <div className={v.toolbar} role='toolbar' aria-label='Playback'>
      <div className={v.group}>
        <button onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <span className={v.zoom}>{fmtTime(t)} / {fmtTime(dur)}</span>
        <button aria-pressed={loop} onClick={() => setLoop(x => !x)} disabled={!range} aria-label='Loop the selected range'><Repeat size={15} /></button>
        {range && <span className={v.hint}>Selected {fmtTime(range[0])} – {fmtTime(range[1])} <button className={v.textBtn} onClick={() => { setRange(null); setLoop(false); }}>clear</button></span>}
      </div>
    </div>
    <div className={v.wave} onPointerDown={e => { (e.target as HTMLElement).setPointerCapture?.(e.pointerId); drag.current = at(e.clientX, e.currentTarget); }}
      onPointerMove={e => { if (drag.current !== null) { const b = at(e.clientX, e.currentTarget); if (Math.abs(b - drag.current) > dur / 400) setRange([Math.min(drag.current, b), Math.max(drag.current, b)]); } }}
      onPointerUp={e => { const a = drag.current, b = at(e.clientX, e.currentTarget); drag.current = null; if (a !== null && Math.abs(b - a) <= dur / 400 && audio.current) audio.current.currentTime = b; }}
      role='slider' aria-label='Waveform: click to seek, drag to select a range' aria-valuemin={0} aria-valuemax={Math.round(dur)} aria-valuenow={Math.round(t)} tabIndex={0}
      onKeyDown={e => { if (!audio.current) return; if (e.key === 'ArrowRight') audio.current.currentTime = t + 1; if (e.key === 'ArrowLeft') audio.current.currentTime = Math.max(0, t - 1); }}>
      {peaks ? <canvas ref={canvas} /> : <div className={v.waveEmpty}>{problem ?? 'Decoding the working copy…'}</div>}
      {dur > 0 && timed.map(f => f.location.kind === 'time' && <button key={f.id} className={v.interval} data-on={selected?.id === f.id || undefined} data-level={f.level}
        style={{ left: pct(f.location.start), width: `max(3px, ${pct(f.location.end - f.location.start)})` }} onPointerDown={e => e.stopPropagation()}
        onClick={() => onSelect(f.id)} aria-label={`Interval recorded by ${f.moduleId}: ${f.title}`} />)}
      {range && <div className={v.selection} style={{ left: pct(range[0]), width: pct(range[1] - range[0]) }} aria-hidden='true' />}
      <div className={v.playhead} style={{ left: pct(t) }} aria-hidden='true' />
    </div>
    {spectrogram && <figure className={v.spectro}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {/* the spectrogram covers the duration it records, which can be shorter than the file (analysis caps its input) */}
      <img src={api.analysis.artifactUrl(spectrogram.artifact_id)} alt='Spectrogram produced by the analysis'
        style={{ width: dur ? `${Math.min(100, (Number(spectrogram.attributes.duration_s ?? dur) / dur) * 100)}%` : '100%' }} />
      {dur > 0 && <div className={v.playhead} style={{ left: pct(t) }} aria-hidden='true' />}
      <figcaption>Spectrogram (stored artifact): 0 – {Math.round(Number(spectrogram.attributes.top_hz ?? 0))} Hz bottom to top, {Number(spectrogram.attributes.duration_s ?? 0).toFixed(1)} s.</figcaption>
    </figure>}
    <p className={v.canvasNote}>{timed.length ? `${timed.length} finding${timed.length === 1 ? '' : 's'} recorded a time range; choosing one plays and loops exactly that interval.` : 'No finding recorded a time range in this audio.'} The waveform is drawn from the 16 kHz working copy the analysis stored.</p>
  </div>;
}
