'use client';

/* The workspace shell shared by every application page (Flowchart B): global navigation, breadcrumbs,
   search, system status, job monitor and notifications link, and the one live-events connection.
   Each page loads its own data through the API layer; the shell holds no copy of investigation records. */
import { createContext, Suspense, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, TriangleAlert } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { NAV } from '@/config/navigation';
import { CaseContextProvider, useCaseContext } from '@/state/CaseContext';
import { LiveEventsProvider } from '@/api/live';
import { Skeleton } from '@/components/ui';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import SearchPalette from './SearchPalette';
import JobMonitor from './JobMonitor';
import { OfflineBanner } from './SystemStatus';

type Toast = { msg: string; tone: 'ok' | 'alert' };
type Shell = { notify: (msg: string, tone?: Toast['tone']) => void; openPalette: () => void; openJobs: () => void };
const ShellCtx = createContext<Shell | null>(null);
export const useWorkspace = () => { const v = useContext(ShellCtx); if (!v) throw new Error('useWorkspace outside MainLayout'); return v; };

export default function MainLayout({ children }: { children: ReactNode }) {
  // search params are read below, so the shell renders inside a Suspense boundary (Next.js 16)
  return <Suspense fallback={<ShellFallback />}><LiveEventsProvider><CaseContextProvider><Shell>{children}</Shell></CaseContextProvider></LiveEventsProvider></Suspense>;
}

function ShellFallback() {
  return <div className={s.app}><aside className={s.rail} /><div className={s.surface}><div className={s.page} aria-busy='true'><Skeleton h={30} w={260} /><Skeleton h={14} w={420} style={{ marginTop: 14 }} /></div></div></div>;
}

function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { caseId } = useCaseContext();
  const [rail, setRail] = useState(false);
  const [mobileRail, setMobileRail] = useState(false);
  const [palette, setPalette] = useState(false);
  const [jobs, setJobs] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => { try { const v = localStorage.getItem('nx-rail'); setRail(v ? v === '1' : matchMedia('(min-width: 1360px)').matches); } catch { /* defaults */ } }, []);
  const toggleRail = useCallback(() => setRail(v => { try { localStorage.setItem('nx-rail', v ? '0' : '1'); } catch { /* ignore */ } return !v; }), []);
  const notify = useCallback((msg: string, tone: Toast['tone'] = 'ok') => { setToast({ msg, tone }); clearTimeout(timer.current); timer.current = setTimeout(() => setToast(null), 4600); }, []);

  useEffect(() => { setMobileRail(false); setPalette(false); setJobs(false); }, [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(p => !p); return; }
      if (mod && e.key.toLowerCase() === 'b') { e.preventDefault(); toggleRail(); return; }
      if ((e.target as HTMLElement).closest('input, textarea, select, [contenteditable]') || palette || jobs) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 9 && !mod && !e.altKey && NAV[n - 1]) {
        const item = NAV[n - 1];
        router.push(item.scoped && caseId ? `${item.href}?case=${encodeURIComponent(caseId)}` : item.href);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleRail, palette, jobs, router, caseId]);

  const menuBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!mobileRail) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMobileRail(false); };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); menuBtn.current?.focus({ preventScroll: true }); };
  }, [mobileRail]);

  // tabs inside one investigation or one evidence item keep a single key, so their frame does not remount
  const routeKey = pathname.replace(/^(\/(investigations|evidence)\/[^/]+)(\/.*)?$/, '$1');
  const shell: Shell = { notify, openPalette: () => setPalette(true), openJobs: () => setJobs(true) };

  return <ShellCtx.Provider value={shell}>
    <div className={`${s.app} ${rail ? s.railOpen : ''}`}>
      {mobileRail && <button className={s.scrim} style={{ zIndex: 29, border: 0, cursor: 'default' }} onClick={() => setMobileRail(false)} aria-label='Close navigation' tabIndex={-1} />}
      <Sidebar open={mobileRail} rail={rail} toggleRail={toggleRail} />
      <div className={s.surface} inert={mobileRail || undefined}>
        <Topbar menuRef={menuBtn} onMenu={() => setMobileRail(true)} menuOpen={mobileRail} onPalette={() => setPalette(true)} onJobs={() => setJobs(true)} />
        <OfflineBanner />
        <motion.main key={routeKey} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }}>{children}</motion.main>
      </div>
      <SearchPalette open={palette} onClose={() => setPalette(false)} toggleRail={toggleRail} />
      <JobMonitor open={jobs} onClose={() => setJobs(false)} />
      <AnimatePresence>{toast && <motion.div className={s.toast} role='status' style={toast.tone === 'alert' ? { borderColor: '#f0604d66', background: '#1f1311' } : undefined} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
        {toast.tone === 'alert' ? <TriangleAlert size={16} style={{ color: 'var(--alert)' }} /> : <Check size={16} />}{toast.msg}
      </motion.div>}</AnimatePresence>
    </div>
  </ShellCtx.Provider>;
}
