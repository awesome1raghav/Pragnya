'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Aperture, Info, PanelLeftClose, PanelLeftOpen, Plus } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { NAV, NAV_GROUPS, isActive } from '@/config/navigation';
import { paths } from '@/config/routes';
import { useCase } from '@/api/hooks';
import { useCaseContext } from '@/state/CaseContext';

/* Global navigation in three groups: the investigation and its evidence, the analytical workspaces, and operating
   the installation. The investigation in context is shown above them; pages that work within an investigation
   (Evidence, Sources, Lineage, Intelligence, Graph, Reports) keep it in their link. */
export default function Sidebar({ open, rail, toggleRail }: { open: boolean; rail: boolean; toggleRail: () => void }) {
  const pathname = usePathname();
  const { caseId } = useCaseContext();
  return <aside className={`${s.rail} ${open ? s.railMobile : ''}`} aria-label='Workspace navigation' role={open ? 'dialog' : undefined} aria-modal={open || undefined}>
    <Link href={paths.dashboard()} className={s.brand} aria-label='NEXTRON dashboard'><Aperture /><span>NEXTRON</span></Link>
    <Link href={paths.newInvestigation()} className={`${s.railItem} ${s.tip} ${s.railNew}`} data-tip='New investigation'><Plus size={18} /><span>New investigation</span></Link>
    {caseId && <ActiveCase caseId={caseId} />}
    <nav className={s.railNav} aria-label='Destinations'>
      {NAV_GROUPS.map(g => <div key={g.id} className={s.railGroup} role='group' aria-label={g.label}>
        <span className={s.railLabel} aria-hidden='true'>{g.label}</span>
        {NAV.map((item, i) => item.group !== g.id ? null : <NavItem key={item.href} item={item} index={i} pathname={pathname} caseId={caseId} />)}
      </div>)}
    </nav>
    <div className={s.railFoot}>
      <button className={`${s.railItem} ${s.tip}`} data-tip='Expand · Ctrl B' onClick={toggleRail} aria-label={rail ? 'Collapse sidebar' : 'Expand sidebar'}>{rail ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}<span>Collapse</span></button>
      <Link href={paths.about()} className={`${s.railItem} ${s.tip}`} data-tip='About NEXTRON'><Info size={18} /><span>About NEXTRON</span></Link>
      <div title='Single-operator local mode: no sign-in; the API accepts requests from this machine only'><span className={s.avatar}>OP</span><div><b>Local operator</b><small>Single-user mode, no sign-in</small></div></div>
    </div>
  </aside>;
}

function NavItem({ item, index, pathname, caseId }: { item: (typeof NAV)[number]; index: number; pathname: string; caseId: string | null }) {
  const { href, label, icon: Icon, match, scoped } = item;
  const on = isActive(pathname, match);
  const to = scoped && caseId ? `${href}?case=${encodeURIComponent(caseId)}` : href;
  return <Link href={to} data-tip={index < 9 ? `${label} · ${index + 1}` : label} className={`${s.railItem} ${s.tip} ${on ? s.railOn : ''}`} aria-current={on ? 'page' : undefined} aria-label={label}>
    <Icon size={18} /><span>{label}</span>{index < 9 && <kbd>{index + 1}</kbd>}
  </Link>;
}

/** The investigation the scoped pages work in: one click back to it from anywhere. */
function ActiveCase({ caseId }: { caseId: string }) {
  const c = useCase(caseId).data;
  if (!c) return null;
  return <Link href={paths.case(c.case_id)} className={`${s.railCase} ${s.tip}`} data-tip={`In context: ${c.case_number}`} aria-label={`Investigation in context: ${c.case_number} ${c.title}`}>
    <i aria-hidden='true' /><span><small>{c.case_number}</small><b>{c.title}</b></span>
  </Link>;
}
