'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import { Aperture, ArrowLeft, Bell, ChevronRight, FileText, LayoutGrid, Menu, Microscope, PanelLeftClose, PanelLeftOpen, RotateCcw, Scale, Search, Share2, Upload, Check } from 'lucide-react';
import s from './workspace.module.css';
import type { Tool, View } from './data';
import { Skeleton, type Ctx } from './ui';
import { WorkspaceData, useData } from './store';
import Palette from './palette';
import Command from './command';
import Investigate from './investigate';
import Graph from './graph';
import Intake from './intake';
import { Report, Audit } from './deliver';

const VIEWS: { id: View; label: string; icon: typeof LayoutGrid }[] = [
  { id: 'command', label: 'Command centre', icon: LayoutGrid },
  { id: 'investigate', label: 'Investigation', icon: Microscope },
  { id: 'graph', label: 'Evidence graph', icon: Share2 },
  { id: 'intake', label: 'Scan evidence', icon: Upload },
  { id: 'report', label: 'Report studio', icon: FileText },
  { id: 'audit', label: 'Governance', icon: Scale },
];
const TOOL_LABEL: Record<Tool, string> = { viewer: 'Viewer', frames: 'Frames', timeline: 'Timeline', metadata: 'Metadata' };

export default function Page() { return <WorkspaceData><Workspace /></WorkspaceData>; }

function Workspace() {
  const data = useData();
  const [view, setView] = useState<View>('command');
  const [caseId, setCase] = useState('');
  const [evidenceId, setEvidence] = useState('');
  const [tool, setTool] = useState<Tool>('viewer');
  const [finding, setFinding] = useState<string | null>(null);
  const [runId, setRunId] = useState(0);
  const [rail, setRail] = useState(false);
  const [mobileRail, setMobileRail] = useState(false);
  const [palette, setPalette] = useState(false);
  const [toast, setToast] = useState<{ msg: string; undo?: () => void } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // when data arrives, focus the most urgent case and its first evidence
  useEffect(() => {
    if (data.status !== 'ready' || caseId) return;
    const top = [...data.cases].sort((a, b) => b.priority - a.priority)[0];
    if (top) { setCase(top.id); setEvidence(data.evidence.find(e => e.caseId === top.id)?.id ?? ''); }
  }, [data.status, data.cases, data.evidence, caseId]);

  useEffect(() => { try { setRail(localStorage.getItem('nx-rail') === '1'); } catch {} }, []);
  const toggleRail = useCallback(() => setRail(v => { try { localStorage.setItem('nx-rail', v ? '0' : '1'); } catch {} return !v; }), []);

  const go: Ctx['go'] = useCallback((v, o = {}) => {
    if (o.caseId) { setCase(o.caseId); if (!o.evidence) setEvidence(data.evidence.find(e => e.caseId === o.caseId)?.id ?? ''); }
    if (o.evidence) { setEvidence(o.evidence); const e = data.evidence.find(x => x.id === o.evidence); if (e) setCase(e.caseId); }
    if (o.tool) setTool(o.tool);
    setFinding(o.finding ?? null);
    if (o.run) setRunId(n => n + 1);
    setView(v); setMobileRail(false); setPalette(false);
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [data.evidence]);
  const notify: Ctx['notify'] = useCallback((msg, undo) => { setToast({ msg, undo }); clearTimeout(timer.current); timer.current = setTimeout(() => setToast(null), 4200); }, []);

  const c = data.cases.find(x => x.id === caseId);
  const ev = data.evidence.find(x => x.id === evidenceId);
  const current = VIEWS.find(v => v.id === view)!;
  useEffect(() => { document.title = `${current.label} — NEXTRON`; }, [current.label]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(p => !p); return; }
      if (mod && e.key.toLowerCase() === 'b') { e.preventDefault(); toggleRail(); return; }
      if ((e.target as HTMLElement).closest('input, textarea, select, [contenteditable]') || palette) return;
      if (/^[1-6]$/.test(e.key) && !mod && !e.altKey) go(VIEWS[Number(e.key) - 1].id, { caseId });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, toggleRail, palette, caseId]);

  const ctx: Ctx = { go, notify, caseId, evidenceId };
  const crumbs: { label: React.ReactNode; on?: () => void }[] = [{ label: 'Workspace', on: () => go('command') }];
  if (c && (view === 'investigate' || view === 'graph' || view === 'report')) {
    crumbs.push({ label: c.name, on: () => go('investigate', { caseId }) });
    if (view === 'investigate' && ev) { crumbs.push({ label: <span className={s.mono}>{ev.fileName}</span>, on: () => go('investigate', { evidence: ev.id, tool: 'viewer' }) }); crumbs.push({ label: TOOL_LABEL[tool] }); }
    else crumbs.push({ label: current.label });
  } else crumbs.push({ label: current.label });

  const ready = data.status === 'ready' && c;

  return <div className={`${s.app} ${rail ? s.railOpen : ''}`}>
    {mobileRail && <div className={s.scrim} style={{ zIndex: 29 }} onClick={() => setMobileRail(false)} aria-hidden='true' />}
    <aside className={`${s.rail} ${mobileRail ? s.railMobile : ''}`} aria-label='Workspace navigation'>
      <Link href='/' className={s.brand} aria-label='NEXTRON home'><Aperture /><span>NEXTRON</span></Link>
      {VIEWS.map(({ id, label, icon: Icon }, i) => <button key={id} data-tip={`${label} · ${i + 1}`} className={`${s.railItem} ${s.tip} ${view === id ? s.railOn : ''}`} aria-current={view === id ? 'page' : undefined} onClick={() => go(id, { caseId })} aria-label={label}><Icon size={18} /><span>{label}</span><kbd>{i + 1}</kbd></button>)}
      <div className={s.railFoot}>
        <button className={`${s.railItem} ${s.tip}`} data-tip='Expand · Ctrl B' onClick={toggleRail} aria-label={rail ? 'Collapse sidebar' : 'Expand sidebar'}>{rail ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}<span>Collapse</span></button>
        <Link href='/' className={`${s.railItem} ${s.tip}`} data-tip='Back to site'><ArrowLeft size={18} /><span>Back to site</span></Link>
        <div><span className={s.avatar}>RC</span><div><b>R. Carter</b><small>Forensic analysis</small></div></div>
      </div>
    </aside>

    <div className={s.surface}>
      <header className={s.top}>
        <button className={`${s.iconBtn} ${s.menuBtn}`} onClick={() => setMobileRail(true)} aria-label='Open navigation'><Menu size={18} /></button>
        <nav className={s.crumbs} aria-label='Breadcrumb'>{crumbs.map((cr, i) => <span key={i}>{i > 0 && <ChevronRight size={14} />}<button className={s.crumb} onClick={cr.on} disabled={!cr.on} aria-current={i === crumbs.length - 1 ? 'page' : undefined}>{cr.label}</button></span>)}</nav>
        <button className={s.cmdk} onClick={() => setPalette(true)} aria-label='Open command palette'><Search size={15} /><span>Search or run a command</span><kbd>Ctrl K</kbd></button>
        <button className={s.iconBtn} aria-label={`Decisions waiting: ${data.decisions.length}`} onClick={() => go('command')}><Bell size={17} />{data.decisions.length > 0 && <i />}</button>
      </header>

      {data.status === 'error' ? <div className={s.state}><b style={{ color: 'var(--ink)', fontSize: 16 }}>The workspace could not load</b><span>{data.error}</span><button className={s.btn} onClick={data.reload}><RotateCcw size={15} />Try again</button></div>
        : !ready ? <div className={s.page} aria-busy='true'><Skeleton h={30} w={260} /><Skeleton h={14} w={420} style={{ marginTop: 14 }} /><div className={s.bento} style={{ marginTop: 32 }}><Skeleton h={460} r={20} style={{ gridColumn: 'span 8' }} /><Skeleton h={460} r={20} style={{ gridColumn: 'span 4' }} /></div></div>
        : <AnimatePresence mode='wait' initial={false}>
          <motion.main key={view} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }}>
            {view === 'command' && <Command {...ctx} />}
            {view === 'investigate' && <Investigate {...ctx} tool={tool} setTool={setTool} finding={finding} setFinding={setFinding} runId={runId} />}
            {view === 'graph' && <Graph {...ctx} />}
            {view === 'intake' && <Intake {...ctx} />}
            {view === 'report' && <Report {...ctx} />}
            {view === 'audit' && <Audit {...ctx} />}
          </motion.main>
        </AnimatePresence>}
    </div>

    {ready && <Palette open={palette} onClose={() => setPalette(false)} ctx={ctx} toggleRail={toggleRail} />}

    <AnimatePresence>{toast && <motion.div className={s.toast} role='status' initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
      <Check size={16} />{toast.msg}{toast.undo && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => { toast.undo!(); setToast(null); }}>Undo</button>}
    </motion.div>}</AnimatePresence>
  </div>;
}
