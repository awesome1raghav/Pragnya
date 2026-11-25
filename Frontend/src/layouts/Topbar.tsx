'use client';

import Link from 'next/link';
import { Bell, Menu, Search } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import { paths } from '@/config/routes';
import Breadcrumbs from './Breadcrumbs';

export default function Topbar({ menuRef, onMenu, menuOpen, onPalette }: { menuRef: React.RefObject<HTMLButtonElement | null>; onMenu: () => void; menuOpen: boolean; onPalette: () => void; caseId: string }) {
  const { decisions, status } = useData();
  return <header className={s.top}>
    <button ref={menuRef} className={`${s.iconBtn} ${s.menuBtn}`} onClick={onMenu} aria-label='Open navigation' aria-expanded={menuOpen}><Menu size={18} /></button>
    {status === 'ready' ? <Breadcrumbs /> : <span />}
    <button className={s.cmdk} onClick={onPalette} aria-label='Open command palette'><Search size={15} /><span>Search or run a command</span><kbd>Ctrl K</kbd></button>
    <Link className={s.iconBtn} href={paths.notifications()} aria-label={`Notifications: ${decisions.length} decisions waiting`}><Bell size={17} />{decisions.length > 0 && <i />}</Link>
  </header>;
}
