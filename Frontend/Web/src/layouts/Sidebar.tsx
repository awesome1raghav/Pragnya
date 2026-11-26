'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Aperture, Info, PanelLeftClose, PanelLeftOpen, Plus } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { NAV, isActive } from '@/config/navigation';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';

/* Global navigation. Pages that work within an investigation (Evidence, Sources, Lineage, Intelligence,
   Graph, Reports) keep the active investigation in their link, so moving between them keeps context. */
export default function Sidebar({ open, rail, toggleRail }: { open: boolean; rail: boolean; toggleRail: () => void }) {
  const pathname = usePathname();
  const { caseId } = useCaseContext();
  return <aside className={`${s.rail} ${open ? s.railMobile : ''}`} aria-label='Workspace navigation' role={open ? 'dialog' : undefined} aria-modal={open || undefined}>
    <Link href={paths.dashboard()} className={s.brand} aria-label='NEXTRON dashboard'><Aperture /><span>NEXTRON</span></Link>
    <Link href={paths.newInvestigation()} className={`${s.railItem} ${s.tip} ${s.railNew}`} data-tip='New investigation'><Plus size={18} /><span>New investigation</span></Link>
    {NAV.map(({ href, label, icon: Icon, match, scoped }, i) => {
      const on = isActive(pathname, match);
      const to = scoped && caseId ? `${href}?case=${encodeURIComponent(caseId)}` : href;
      return <Link key={href} href={to} data-tip={i < 9 ? `${label} · ${i + 1}` : label} className={`${s.railItem} ${s.tip} ${on ? s.railOn : ''}`} aria-current={on ? 'page' : undefined} aria-label={label}><Icon size={18} /><span>{label}</span>{i < 9 && <kbd>{i + 1}</kbd>}</Link>;
    })}
    <div className={s.railFoot}>
      <button className={`${s.railItem} ${s.tip}`} data-tip='Expand · Ctrl B' onClick={toggleRail} aria-label={rail ? 'Collapse sidebar' : 'Expand sidebar'}>{rail ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}<span>Collapse</span></button>
      <Link href={paths.about()} className={`${s.railItem} ${s.tip}`} data-tip='About NEXTRON'><Info size={18} /><span>About NEXTRON</span></Link>
      <div title='Single-operator local mode: no sign-in; the API accepts requests from this machine only'><span className={s.avatar}>OP</span><div><b>Local operator</b><small>Single-user mode, no sign-in</small></div></div>
    </div>
  </aside>;
}
