'use client';

import Link from 'next/link';
import { Activity, Bell, Menu, Search } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { paths } from '@/config/routes';
import p from '@/styles/platform.module.css';
import { useNotificationSummary } from '@/api/hooks';
import Breadcrumbs from './Breadcrumbs';
import SystemStatus from './SystemStatus';

export default function Topbar({ menuRef, onMenu, menuOpen, onPalette, onJobs }: { menuRef: React.RefObject<HTMLButtonElement | null>; onMenu: () => void; menuOpen: boolean; onPalette: () => void; onJobs: () => void }) {
  return <header className={s.top}>
    <button ref={menuRef} className={`${s.iconBtn} ${s.menuBtn}`} onClick={onMenu} aria-label='Open navigation' aria-expanded={menuOpen}><Menu size={18} /></button>
    <Breadcrumbs />
    <button className={s.cmdk} onClick={onPalette} title='Search everything, or run a command (Ctrl K)' aria-label='Search investigations, evidence, sources, findings, reports and reviews, or run a command'><Search size={15} /><span>Search or run a command</span><kbd>Ctrl K</kbd></button>
    <SystemStatus />
    <button className={s.iconBtn} onClick={onJobs} aria-label='Open the job monitor' title='Job monitor'><Activity size={17} /></button>
    <NotificationsLink />
  </header>;
}

function NotificationsLink() {
  const unread = useNotificationSummary().data?.unread ?? 0;
  return <Link className={s.iconBtn} href={paths.notifications()} aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'} style={{ position: 'relative' }}>
    <Bell size={17} />{unread > 0 && <span className={p.badge} aria-hidden='true'>{unread > 99 ? '99+' : unread}</span>}
  </Link>;
}
