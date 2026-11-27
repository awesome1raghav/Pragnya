'use client';

/* Evidence entries, title first. Image entries show the stored original itself (served by the API), never a stand-in
   picture; video and audio show their type. One quiet line carries the identifier, type, size and investigation. */
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ChevronRight, Film, ImageIcon, Waves } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import x from './evidence.module.css';
import { api, type Evidence, type EvidenceListItem } from '@/api';
import { paths } from '@/config/routes';
import { ago, bytes, mediaLabel } from '@/utils/labels';

export const mediaIcon = (t: Evidence['media_type']) => (t === 'IMAGE' ? ImageIcon : t === 'VIDEO' ? Film : Waves);

export function MediaThumb({ ev, className = x.thumb, size = 18 }: { ev: Evidence; className?: string; size?: number }) {
  if (ev.media_type === 'IMAGE') return <span className={className}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={api.evidence.previewUrl(ev.evidence_id)} alt='' loading='lazy' /></span>;
  const Icon = mediaIcon(ev.media_type);
  return <span className={className} aria-hidden='true'><Icon size={size} /></span>;
}

const line = (ev: Evidence | EvidenceListItem, showCase?: boolean) => [ev.evidence_number, `${mediaLabel[ev.media_type]} ${ev.mime_type.split('/')[1] ?? ''}`.trim(), bytes(ev.file_size),
  showCase && 'case_number' in ev ? `${ev.case_number} ${ev.case_title}` : null, ev.description].filter(Boolean).join(' · ');

export default function EvidenceRows({ items, showCase }: { items: (Evidence | EvidenceListItem)[]; showCase?: boolean }) {
  return <ul className={`${x.list} ${x.ev}`}>{items.map((ev, i) => <motion.li key={ev.evidence_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 10) * 0.015, duration: .16 }}>
    <Link className={x.row} href={paths.evidence(ev.evidence_id)}>
      <MediaThumb ev={ev} />
      <span className={x.main}><b title={ev.filename}>{ev.filename}</b><small title={ev.sha256}>{line(ev, showCase)}</small></span>
      <time className={x.when} dateTime={ev.received_at} title={ev.received_at}>{ago(ev.received_at)}</time>
      <ChevronRight size={16} className={s.rowChev} />
    </Link>
  </motion.li>)}</ul>;
}

export function EvidenceBoard({ items, showCase }: { items: (Evidence | EvidenceListItem)[]; showCase?: boolean }) {
  return <div className={`${x.board} ${x.ev}`}>{items.map((ev, i) => <motion.div key={ev.evidence_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.025, duration: .22, ease: [.22, 1, .36, 1] }}>
    <Link className={x.tile} href={paths.evidence(ev.evidence_id)} aria-label={`${ev.evidence_number} ${ev.filename}`}>
      <MediaThumb ev={ev} className={x.tileMedia} size={24} />
      <span className={x.tileBody}><b title={ev.filename}>{ev.filename}</b><small>{line(ev, showCase)}</small><small>received {ago(ev.received_at)}</small></span>
    </Link>
  </motion.div>)}</div>;
}
