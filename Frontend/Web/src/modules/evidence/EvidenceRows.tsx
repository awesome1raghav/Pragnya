'use client';

/* One row per preserved evidence item. Image rows show the stored original itself (served by the API),
   never a stand-in picture; video and audio show their type until frames are extracted (plan Step 4). */
import Link from 'next/link';
import { ChevronRight, Film, ImageIcon, Waves } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, type Evidence, type EvidenceListItem } from '@/api';
import { paths } from '@/config/routes';
import { ago, bytes, mediaLabel } from '@/utils/labels';

export function MediaThumb({ ev }: { ev: Evidence }) {
  if (ev.media_type === 'IMAGE') return <span className={p.media}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={api.evidence.previewUrl(ev.evidence_id)} alt='' loading='lazy' /></span>;
  return <span className={p.media} aria-hidden='true'>{ev.media_type === 'VIDEO' ? <Film size={18} /> : <Waves size={18} />}</span>;
}

export const mediaIcon = (t: Evidence['media_type']) => (t === 'IMAGE' ? ImageIcon : t === 'VIDEO' ? Film : Waves);

export default function EvidenceRows({ items, showCase }: { items: (Evidence | EvidenceListItem)[]; showCase?: boolean }) {
  return <div className={p.evList}>
    <div className={`${p.evRow} ${p.listHead}`} aria-hidden='true'><span>Evidence</span><span /><span>File</span><span>Type</span><span>{showCase ? 'Investigation' : 'SHA-256'}</span><span>Received</span><span /></div>
    <ul className={s.list}>{items.map(ev => <li key={ev.evidence_id}><Link className={p.evRow} href={paths.evidence(ev.evidence_id)}>
      <b>{ev.evidence_number}</b>
      <MediaThumb ev={ev} />
      <span className={p.rowMain}><b title={ev.filename}>{ev.filename}</b><small>{ev.mime_type} · {bytes(ev.file_size)}{ev.description ? ` · ${ev.description}` : ''}</small></span>
      <span className={p.rowNum}>{mediaLabel[ev.media_type]}</span>
      {showCase && 'case_number' in ev ? <span className={p.rowMain}><b className={s.mono} style={{ fontSize: 12 }}>{ev.case_number}</b><small>{ev.case_title}</small></span> : <span className={`${s.mono} ${p.rowNum}`} title={ev.sha256}>{ev.sha256.slice(0, 12)}…</span>}
      <time className={p.rowTime} dateTime={ev.received_at} title={ev.received_at}>{ago(ev.received_at)}</time>
      <ChevronRight size={16} className={s.rowChev} />
    </Link></li>)}</ul>
  </div>;
}
