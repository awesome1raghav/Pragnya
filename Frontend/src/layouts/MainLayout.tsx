'use client';

/* The investigation workspace shell, shared by every workspace route.
   - Data loads once here (WorkspaceData) and survives navigation between pages.
   - The current case and evidence come from the URL (/investigations/:caseId…, /evidence/:evidenceId…,
     /reports/:reportId…); pages without one fall back to the most urgent case.
   - `go()` is the single way screens navigate: it turns an intent ("open this finding") into an address. */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { WorkspaceData, useData } from '@/stores/workspace.store';
import { Skeleton, type Ctx } from '@/components/ui';
import { paths } from '@/config/routes';
import { NAV } from '@/config/navigation';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import CommandPalette from './CommandPalette';

type Shell = Ctx & { rail: boolean; toggleRail: () => void; openPalette: () => void };
const ShellCtx = createContext<Shell | null>(null);
export const useWorkspace = () => { const v = useContext(ShellCtx); if (!v) throw new Error('useWorkspace outside MainLayout'); return v; };

export default function MainLayout({ children }: { children: ReactNode }) {
  return <WorkspaceData><Shell>{children}</Shell></WorkspaceData>;
}

function Shell({ children }: { children: ReactNode }) {
  const data = useData();
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ caseId?: string; evidenceId?: string; reportId?: string }>();
  const [rail, setRail] = useState(false);
  const [mobileRail, setMobileRail] = useState(false);
  const [palette, setPalette] = useState(false);
  const [toast, setToast] = useState<{ msg: string; undo?: () => void } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  /* where we are: case and evidence named by the address, or sensible defaults */
  const top = useMemo(() => [...data.cases].sort((a, b) => b.priority - a.priority)[0], [data.cases]);
  const routeEv = params.evidenceId ? data.evidence.find(e => e.id === decodeURIComponent(params.evidenceId!)) : undefined;
  const routeCase = decodeURIComponent(params.caseId ?? params.reportId ?? '') || routeEv?.caseId;
  const caseId = routeCase || top?.id || '';
  const evidenceId = routeEv?.id ?? data.evidence.find(e => e.caseId === caseId)?.id ?? '';
  const missing = data.status === 'ready' && ((params.evidenceId && !routeEv) || (routeCase && !data.cases.some(c => c.id === routeCase)));

  // labelled rail by default where there is room for it; icon-only stays a choice the user can make (Ctrl B)
  useEffect(() => { try { const v = localStorage.getItem('nx-rail'); setRail(v ? v === '1' : matchMedia('(min-width: 1360px)').matches); } catch {} }, []);
  const toggleRail = useCallback(() => setRail(v => { try { localStorage.setItem('nx-rail', v ? '0' : '1'); } catch {} return !v; }), []);

  const go: Ctx['go'] = useCallback((view, o = {}) => {
    const cid = o.caseId ?? (o.evidence ? data.evidence.find(e => e.id === o.evidence)?.caseId : undefined) ?? caseId;
    let url = paths.dashboard();
    if (view === 'case') url = paths.case(cid);
    else if (view === 'investigate') {
      const eid = o.evidence ?? (o.caseId ? data.evidence.find(e => e.caseId === o.caseId)?.id : evidenceId);
      if (!eid) url = paths.caseEvidence(cid);
      else {
        const q = new URLSearchParams();
        if (o.finding) q.set('finding', o.finding);
        if (o.run) q.set('run', String(Date.now()));
        url = paths.evidence(eid, o.tool ?? 'viewer') + (q.size ? `?${q}` : '');
      }
    }
    else if (view === 'graph') url = o.caseId ? paths.caseGraph(o.caseId) : paths.graph();
    else if (view === 'intake') url = o.caseId ? paths.caseAddEvidence(o.caseId) : paths.newInvestigation();
    else if (view === 'report') url = paths.caseReport(cid);
    else if (view === 'audit') url = paths.system();
    setMobileRail(false); setPalette(false);
    router.push(url);
  }, [router, data.evidence, caseId, evidenceId]);
  const notify: Ctx['notify'] = useCallback((msg, undo) => { setToast({ msg, undo }); clearTimeout(timer.current); timer.current = setTimeout(() => setToast(null), 4200); }, []);

  useEffect(() => { setMobileRail(false); }, [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(p => !p); return; }
      if (mod && e.key.toLowerCase() === 'b') { e.preventDefault(); toggleRail(); return; }
      if ((e.target as HTMLElement).closest('input, textarea, select, [contenteditable]') || palette) return;
      const n = Number(e.key);
      if (n >= 1 && n <= NAV.length && !mod && !e.altKey) router.push(NAV[n - 1].href);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleRail, palette, router]);

  // phone navigation: Escape closes it; focus moves in, then back to the menu button
  const menuBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!mobileRail) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMobileRail(false); };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); menuBtn.current?.focus({ preventScroll: true }); };
  }, [mobileRail]);

  const shell: Shell = { go, notify, caseId, evidenceId, rail, toggleRail, openPalette: () => setPalette(true) };
  // the evidence workbench keeps one key across its tools, so switching tools never remounts it
  const routeKey = pathname.replace(/^(\/evidence\/[^/]+)\/(analysis|timeline|metadata|preview)$/, '$1');
  const ready = data.status === 'ready' && top;

  return <ShellCtx.Provider value={shell}>
    <div className={`${s.app} ${rail ? s.railOpen : ''}`}>
      {mobileRail && <button className={s.scrim} style={{ zIndex: 29, border: 0, cursor: 'default' }} onClick={() => setMobileRail(false)} aria-label='Close navigation' tabIndex={-1} />}
      <Sidebar open={mobileRail} rail={rail} toggleRail={toggleRail} />
      <div className={s.surface} inert={mobileRail || undefined}>
        <Topbar menuRef={menuBtn} onMenu={() => setMobileRail(true)} menuOpen={mobileRail} onPalette={() => setPalette(true)} caseId={caseId} />
        {data.status === 'error' ? <div className={s.state}><b style={{ color: 'var(--ink)', fontSize: 16 }}>The workspace could not load</b><span>{data.error}</span><button className={s.btn} onClick={data.reload}><RotateCcw size={15} />Try again</button></div>
          : !ready ? <div className={s.page} aria-busy='true'><Skeleton h={30} w={260} /><Skeleton h={14} w={420} style={{ marginTop: 14 }} /><div className={s.bento} style={{ marginTop: 32 }}><Skeleton h={460} r={20} style={{ gridColumn: 'span 8' }} /><Skeleton h={460} r={20} style={{ gridColumn: 'span 4' }} /></div></div>
          : missing ? <div className={s.state}><b style={{ color: 'var(--ink)', fontSize: 18 }}>Nothing found at this address</b><span>No {params.evidenceId ? 'evidence' : 'investigation'} with that ID is in this workspace.</span><button className={s.btn} onClick={() => router.push(paths.investigations())}>All investigations</button></div>
          : <motion.main key={routeKey} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }}>{children}</motion.main>}
      </div>
      {ready && <CommandPalette open={palette} onClose={() => setPalette(false)} ctx={shell} toggleRail={toggleRail} />}
      <AnimatePresence>{toast && <motion.div className={s.toast} role='status' initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
        <Check size={16} />{toast.msg}{toast.undo && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => { toast.undo!(); setToast(null); }}>Undo</button>}
      </motion.div>}</AnimatePresence>
    </div>
  </ShellCtx.Provider>;
}
