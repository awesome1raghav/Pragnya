'use client';

/* /notifications: created by the backend from committed events (run outcomes, failed integrity checks, failed source
   retrievals, reports). Grouped by what they ask of the operator: "Needs action" (alerts and warnings that are not
   routine), then analysis and other activity, with runs of the same kind collapsed into one line. Only the read state
   changes; notifications are never edited or invented. */
import Link from 'next/link';
import { useState } from 'react';
import { CheckCheck, ChevronDown } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import n from './notifications.module.css';
import { api, ApiError, type Notification } from '@/api';
import { useNotifications } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { Dot, Empty, Load, PageHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { ago, utc, type Tone } from '@/utils/labels';

const tone: Record<Notification['severity'], Tone> = { INFO: 'steel', WARNING: 'gold', ALERT: 'alert' };
const label: Record<Notification['severity'], string> = { INFO: 'Info', WARNING: 'Warning', ALERT: 'Alert' };
type View = 'action' | 'analysis' | 'other' | 'all';
const routine = (x: Notification) => x.event_type === 'job.partially_completed';  // normal when a detector is absent
const kind = (x: Notification): Exclude<View, 'all'> =>
  (x.severity === 'ALERT' || x.severity === 'WARNING') && !routine(x) ? 'action' : x.event_type.startsWith('job.') ? 'analysis' : 'other';
const VIEWS: [View, string][] = [['action', 'Needs action'], ['analysis', 'Analysis'], ['other', 'Reports and sources'], ['all', 'All']];

export default function NotificationsPage() {
  const [unread, setUnread] = useState(false);
  const [view, setView] = useState<View>('action');
  const q = useNotifications(unread);
  const { notify } = useWorkspace();
  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); invalidate('notifications'); } catch (e) { notify(e instanceof ApiError ? e.message : 'The update failed', 'alert'); }
  };
  return <div className={s.page}>
    <PageHead title='Notifications' desc='What needs you first; routine background work collapsed beneath it.'>
      <button className={s.btn} onClick={() => act(async () => { const r = await api.notifications.readAll(); notify(`${r.marked} marked read`); })}><CheckCheck size={15} />Mark all read</button>
    </PageHead>
    <Load q={q} rows={4}>{r => {
      const counts = Object.fromEntries(VIEWS.map(([k]) => [k, k === 'all' ? r.data.length : r.data.filter(x => kind(x) === k).length])) as Record<View, number>;
      const items = view === 'all' ? r.data : r.data.filter(x => kind(x) === view);
      return <>
        <div className={n.bar}>
          <nav className={s.seg} aria-label='Filter notifications'>{VIEWS.map(([k, l]) => <button key={k} aria-selected={view === k} onClick={() => setView(k)}>{l}<span className={s.count}>{counts[k]}</span></button>)}</nav>
          <label className={n.toggle}><input type='checkbox' checked={unread} onChange={e => setUnread(e.target.checked)} />Unread only</label>
        </div>
        <section className={s.panel}>{items.length ? <ol className={n.list}>{groups(items).map(g => <Group key={g[0].notification_id} items={g} act={act} />)}</ol>
          : <Empty title={view === 'action' ? 'Nothing needs action' : unread ? 'Nothing unread here' : 'Nothing here yet'}>{view === 'action' ? 'Failed runs, integrity failures, failed reports and unreachable sources would appear here.' : 'Run outcomes, failed integrity checks, source retrievals and reports appear here.'}</Empty>}</section>
        {r.pagination.total_items > r.data.length && <p className={s.cap} style={{ marginTop: 12 }}>Showing the {r.data.length} most recent of {r.pagination.total_items}.</p>}
      </>;
    }}</Load>
  </div>;
}

/** Consecutive notifications of the same kind and outcome (e.g. twelve completed runs) become one group. */
function groups(items: Notification[]): Notification[][] {
  const out: Notification[][] = [];
  for (const x of items) {
    const last = out.at(-1);
    if (last && last[0].event_type === x.event_type && last[0].severity === x.severity && kind(x) !== 'action') last.push(x); else out.push([x]);
  }
  return out;
}

function Group({ items, act }: { items: Notification[]; act: (fn: () => Promise<unknown>) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  if (items.length === 1) return <Row x={items[0]} act={act} />;
  const unread = items.filter(x => !x.read_at).length;
  return <li className={n.group}>
    <button className={n.groupHead} onClick={() => setOpen(v => !v)} aria-expanded={open}>
      <Dot tone={tone[items[0].severity]}>{label[items[0].severity]}</Dot>
      <span><b>{items.length} × {items[0].title.replace(/^(JOB|RPT|SRC)-\d+\s*(v\d+\s*)?/, '')}</b><small>{ago(items.at(-1)!.created_at)} – {ago(items[0].created_at)}{unread ? ` · ${unread} unread` : ''}</small></span>
      <ChevronDown size={15} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform .2s' }} aria-hidden='true' />
    </button>
    {open && <ol className={n.list}>{items.map(x => <Row key={x.notification_id} x={x} act={act} nested />)}</ol>}
  </li>;
}

function Row({ x, act, nested = false }: { x: Notification; act: (fn: () => Promise<unknown>) => Promise<void>; nested?: boolean }) {
  return <li className={`${p.notifRow} ${nested ? n.nested : ''}`} data-unread={!x.read_at}>
    <Dot tone={tone[x.severity]}>{label[x.severity]}</Dot>
    <div>
      <b>{x.link ? <Link href={x.link} onClick={() => !x.read_at && act(() => api.notifications.read(x.notification_id))}>{x.title}</Link> : x.title}</b>
      {x.body && <p>{x.body}</p>}
      <small title={utc(x.created_at)}>{ago(x.created_at)}{x.read_at ? ' · read' : ''}</small>
    </div>
    {!x.read_at && <button className={`${s.btn} ${s.sm}`} onClick={() => act(() => api.notifications.read(x.notification_id))} aria-label={`Mark “${x.title}” read`}>Mark read</button>}
  </li>;
}
