'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Aperture, ArrowLeft, PanelLeftClose, PanelLeftOpen, Plus } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { NAV, isActive } from '@/config/navigation';
import { paths } from '@/config/routes';

export default function Sidebar({ open, rail, toggleRail }: { open: boolean; rail: boolean; toggleRail: () => void }) {
  const pathname = usePathname();
  return <aside className={`${s.rail} ${open ? s.railMobile : ''}`} aria-label='Workspace navigation' role={open ? 'dialog' : undefined} aria-modal={open || undefined}>
    <Link href={paths.home()} className={s.brand} aria-label='NEXTRON home'><Aperture /><span>NEXTRON</span></Link>
    <Link href={paths.newInvestigation()} className={`${s.railItem} ${s.tip} ${s.railNew}`} data-tip='New investigation'><Plus size={18} /><span>New investigation</span></Link>
    {NAV.map(({ href, label, icon: Icon, match }, i) => {
      const on = isActive(pathname, match);
      return <Link key={href} href={href} data-tip={`${label} · ${i + 1}`} className={`${s.railItem} ${s.tip} ${on ? s.railOn : ''}`} aria-current={on ? 'page' : undefined} aria-label={label}><Icon size={18} /><span>{label}</span><kbd>{i + 1}</kbd></Link>;
    })}
    <div className={s.railFoot}>
      <button className={`${s.railItem} ${s.tip}`} data-tip='Expand · Ctrl B' onClick={toggleRail} aria-label={rail ? 'Collapse sidebar' : 'Expand sidebar'}>{rail ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}<span>Collapse</span></button>
      <Link href={paths.home()} className={`${s.railItem} ${s.tip}`} data-tip='Back to site'><ArrowLeft size={18} /><span>Back to site</span></Link>
      <div><span className={s.avatar}>RC</span><div><b>R. Carter</b><small>Forensic analysis</small></div></div>
    </div>
  </aside>;
}
