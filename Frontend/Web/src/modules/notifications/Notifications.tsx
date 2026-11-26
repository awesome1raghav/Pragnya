'use client';

/* /notifications: created by the backend from committed events (job outcomes, failed integrity checks).
   Each links to what it is about. Only the read state changes; notifications are never edited or invented. */
import Link from 'next/link';
import { useState } from 'react';
import { CheckCheck } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, ApiError, type Notification } from '@/api';
import { useNotifications } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { Dot, Empty, Load, PageHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { ago, utc, type Tone } from '@/utils/labels';

const tone: Record<Notification['severity'], Tone> = { INFO: 'steel', WARNING: 'gold', ALERT: 'alert' };
const label: Record<Notification['severity'], string> = { INFO: 'Info', WARNING: 'Warning', ALERT: 'Alert' };

export default function NotificationsPage() {
  const [unread, setUnread] = useState(false);
  const q = useNotifications(unread);
  const { notify } = useWorkspace();
  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); invalidate('notifications'); } catch (e) { notify(e instanceof ApiError ? e.message : 'The update failed', 'alert'); }
  };
  return <div className={s.page}>
    <PageHead title='Notifications' desc='Job outcomes and integrity failures, created from NEXTRON’s committed event stream.'>
      <button className={s.btn} onClick={() => act(async () => { const r = await api.notifications.readAll(); notify(`${r.marked} marked read`); })}><CheckCheck size={15} />Mark all read</button>
    </PageHead>
    <nav className={`${s.seg} ${s.subTabs}`} aria-label='Filter notifications' style={{ marginBottom: 20 }}>
      <button aria-selected={!unread} onClick={() => setUnread(false)}>All</button>
      <button aria-selected={unread} onClick={() => setUnread(true)}>Unread</button>
    </nav>
    <section className={s.panel}>
      <Load q={q} rows={4}>{r => r.data.length ? <ul className={p.jobList}>{r.data.map(n => <li key={n.notification_id} className={p.notifRow} data-unread={!n.read_at}>
        <Dot tone={tone[n.severity]}>{label[n.severity]}</Dot>
        <div>
          <b>{n.link ? <Link href={n.link} onClick={() => !n.read_at && act(() => api.notifications.read(n.notification_id))}>{n.title}</Link> : n.title}</b>
          {n.body && <p>{n.body}</p>}
          <small title={utc(n.created_at)}>{ago(n.created_at)}{n.read_at ? ' · read' : ''}</small>
        </div>
        {!n.read_at && <button className={`${s.btn} ${s.sm}`} onClick={() => act(() => api.notifications.read(n.notification_id))} aria-label={`Mark “${n.title}” read`}>Mark read</button>}
      </li>)}</ul> : <Empty title={unread ? 'Nothing unread' : 'No notifications yet'}>Finished, partial, failed and cancelled jobs, and failed integrity checks, appear here.</Empty>}</Load>
    </section>
  </div>;
}
