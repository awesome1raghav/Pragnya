'use client';

/* Video examination canvas. The preserved original plays as stored. Timeline marks are only the time ranges findings
   recorded; the frame strip is the analysis' own contact sheet (FRAME_SET), each tile placed at the timestamp it records.
   Choosing a finding seeks to its start. Frame stepping uses the frame rate in the extracted metadata when there is one. */
import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { api, type Artifact } from '@/api';
import { fmtTime, type ViewerFinding } from './normalize';
import v from './viewer.module.css';

const SPEEDS = [0.25, 0.5, 1, 1.5, 2];

export function VideoCanvas({ evidenceId, findings, selected, onSelect, sheet, frameRate }: {
  evidenceId: string; findings: ViewerFinding[]; selected: ViewerFinding | null; onSelect: (id: string) => void; sheet: Artifact | null; frameRate: number | null;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timed = findings.filter(f => f.location.kind === 'time');
  const step = frameRate ? 1 / frameRate : 0.04;

  useEffect(() => {
    if (selected?.location.kind !== 'time' || !video.current) return;
    video.current.pause(); video.current.currentTime = selected.location.start;
  }, [selected]);
  useEffect(() => { if (video.current) video.current.playbackRate = speed; }, [speed]);

  const seek = (s: number) => { if (video.current) video.current.currentTime = Math.max(0, Math.min(dur || s, s)); };
  const toggle = () => { const el = video.current; if (!el) return; if (el.paused) void el.play(); else el.pause(); };
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select, button')) return;
      if (e.key === ' ') { e.preventDefault(); toggle(); } else if (e.key === ',') seek(t - step); else if (e.key === '.') seek(t + step);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  const times = (sheet?.attributes.frame_times_s as number[] | undefined) ?? [];
  const tw = Number(sheet?.attributes.width ?? 0), th = Number(sheet?.attributes.height ?? 0);
  const cols = Math.min(4, times.length);
  const rows = Math.ceil(times.length / Math.max(cols, 1));
  const sheetW = cols * (tw + 4) + 4, sheetH = rows * (th + 4) + 4;

  return <div className={v.canvasWrap}>
    <div className={v.videoStage}>
      <video ref={video} src={api.evidence.previewUrl(evidenceId)} preload='metadata' playsInline aria-label='Preserved original video'
        onTimeUpdate={e => setT(e.currentTarget.currentTime)} onLoadedMetadata={e => setDur(e.currentTarget.duration)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onClick={toggle} />
    </div>
    <div className={v.toolbar} role='toolbar' aria-label='Playback'>
      <div className={v.group}>
        <button onClick={() => seek(t - step)} aria-label='Previous frame' title='Previous frame (,)'><ChevronLeft size={15} /></button>
        <button onClick={toggle} aria-label={playing ? 'Pause' : 'Play'} title='Play / pause (space)'>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button onClick={() => seek(t + step)} aria-label='Next frame' title='Next frame (.)'><ChevronRight size={15} /></button>
        <span className={v.zoom}>{fmtTime(t)} / {fmtTime(dur)}</span>
      </div>
      <div className={v.group}>
        <label className={v.select}><span>Speed</span><select value={speed} onChange={e => setSpeed(Number(e.target.value))} aria-label='Playback speed'>{SPEEDS.map(x => <option key={x} value={x}>{x}×</option>)}</select></label>
        <span className={v.hint}>{frameRate ? `${frameRate.toFixed(2)} fps from the metadata` : 'frame rate not recorded: steps of 0.04 s'}</span>
      </div>
    </div>
    <div className={v.timeline} aria-label='Timeline'>
      <input type='range' min={0} max={dur || 0} step={0.001} value={t} onChange={e => seek(Number(e.target.value))} aria-label='Position' className={v.scrub} />
      <div className={v.marks} aria-hidden='true'>{dur > 0 && timed.map(f => f.location.kind === 'time' && <button key={f.id} className={v.mark} data-on={selected?.id === f.id || undefined} data-level={f.level}
        style={{ left: `${(f.location.start / dur) * 100}%`, width: `max(3px, ${((f.location.end - f.location.start) / dur) * 100}%)` }}
        onClick={() => onSelect(f.id)} tabIndex={-1} title={f.title} />)}</div>
    </div>
    {sheet && times.length > 0 && <div className={v.frames} aria-label='Frames the analysis sampled'>{times.map((ft, i) => {
      const cx = 4 + (i % cols) * (tw + 4), cy = 4 + Math.floor(i / cols) * (th + 4);
      return <button key={i} className={v.frame} onClick={() => seek(ft)} data-on={Math.abs(t - ft) < step || undefined} aria-label={`Frame at ${fmtTime(ft)}`}
        style={{ backgroundImage: `url(${api.analysis.artifactUrl(sheet.artifact_id)})`, backgroundSize: `${(sheetW / tw) * 100}% ${(sheetH / th) * 100}%`, backgroundPosition: `${(cx / (sheetW - tw)) * 100}% ${(cy / (sheetH - th || 1)) * 100}%` }}>
        <span>{fmtTime(ft)}</span></button>;
    })}</div>}
    <p className={v.canvasNote}>{timed.length ? `${timed.length} finding${timed.length === 1 ? '' : 's'} recorded a time range; marks on the timeline are exactly those.` : 'No finding recorded a time range in this video.'}
      {sheet ? ' The frame strip shows the frames the analysis sampled (greyscale, as stored).' : ''} No face-level detector is installed, so there is no face localisation.</p>
  </div>;
}
