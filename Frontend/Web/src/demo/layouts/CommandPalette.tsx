'use client';

/* Universal command palette (Ctrl/⌘ K). Every major function is one keystroke away:
   type to filter, ↑ ↓ to move, ↵ to run, Esc to close or step back, and a single letter runs an action
   while the field is empty. "Open investigation" drills into a list of cases. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Columns2, FileSearch, FileText, FolderOpen, LayoutGrid, Microscope, PanelLeft, ScanLine, Scale, Search, Share2, Sparkles, Upload, Film } from 'lucide-react';
import { useRouter } from 'next/navigation';
import s from '@/styles/workspace.module.css';
import { NAV } from '@/demo/config/navigation';
import { branchLabel, statusLabel, statusTone } from '@/demo/utils/labels';
import { useData } from '@/demo/stores/workspace.store';
import type { Media } from '@/demo/api';
import { Dot, Thumb, type Ctx } from '@/demo/components/ui';

type Item = { id: string; group: string; label: string; hint?: string; key?: string; icon?: typeof Search; media?: Media; run: () => void; stay?: boolean };

// subsequence fuzzy match, scored so that word starts and tight runs rank first
function score(q: string, text: string) {
  if (!q) return 1;
  const t = text.toLowerCase(); let i = 0, s = 0, run = 0;
  for (const ch of q.toLowerCase()) {
    const j = t.indexOf(ch, i); if (j < 0) return 0;
    run = j === i ? run + 1 : 0; s += 1 + run * 2 + (j === 0 || t[j - 1] === ' ' ? 3 : 0); i = j + 1;
  }
  return s / t.length;
}

export default function Palette({ open, onClose, ctx, toggleRail }: { open: boolean; onClose: () => void; ctx: Ctx; toggleRail: () => void }) {
  const [q, setQ] = useState('');
  const [page, setPage] = useState<'root' | 'cases'>('root');
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const { go } = ctx;
  const router = useRouter();
  const { cases, evidence, findings } = useData();

  useEffect(() => { if (open) { setQ(''); setPage('root'); setSel(0); requestAnimationFrame(() => input.current?.focus()); } }, [open]);

  const items = useMemo<Item[]>(() => {
    if (page === 'cases') return cases.map(c => ({ id: c.id, group: 'Investigations', label: c.name, hint: c.id, media: c.cover, run: () => go('case', { caseId: c.id }) }));
    const actions: Item[] = [
      { id: 'scan', group: 'Actions', label: 'New investigation', hint: 'Seal and validate a new file', key: 'S', icon: ScanLine, run: () => go('intake') },
      { id: 'deep', group: 'Actions', label: 'Run deepfake analysis', hint: `On ${evidence.find(e => e.id === ctx.evidenceId)?.fileName ?? 'the current file'}`, key: 'D', icon: Sparkles, run: () => go('investigate', { evidence: ctx.evidenceId, tool: 'viewer', run: true }) },
      { id: 'open', group: 'Actions', label: 'Open investigation', hint: `${cases.length} cases`, key: 'O', icon: FolderOpen, run: () => { setPage('cases'); setQ(''); setSel(0); }, stay: true },
      { id: 'meta', group: 'Actions', label: 'Inspect metadata', hint: 'Device, encoder, timestamps', key: 'M', icon: FileSearch, run: () => go('investigate', { evidence: ctx.evidenceId, tool: 'metadata' }) },
      { id: 'cmp', group: 'Actions', label: 'Compare evidence', hint: 'Original against analysis', key: 'C', icon: Columns2, run: () => go('investigate', { evidence: ctx.evidenceId, tool: 'frames' }) },
      { id: 'rep', group: 'Actions', label: 'Generate forensic report', hint: ctx.caseId, key: 'R', icon: FileText, run: () => go('report', { caseId: ctx.caseId }) },
      { id: 'graph', group: 'Actions', label: 'Open evidence graph', hint: 'Relationships across cases', key: 'G', icon: Share2, run: () => go('graph', { caseId: ctx.caseId }) },
    ];
    const nav: Item[] = [
      ...NAV.map(n => ({ id: `n-${n.href}`, group: 'Go to', label: n.label, icon: n.icon as unknown as typeof Search, run: () => router.push(n.href) })),
      { id: 'n-rail', group: 'Go to', label: 'Toggle sidebar', hint: 'Ctrl B', icon: PanelLeft, run: () => { toggleRail(); onClose(); } },
    ];
    if (!q) return [...actions, ...nav];
    const more: Item[] = [
      ...cases.map(c => ({ id: c.id, group: 'Investigations', label: c.name, hint: c.id, media: c.cover, run: () => go('case', { caseId: c.id }) })),
      ...evidence.map(e => ({ id: e.id, group: 'Evidence', label: e.fileName, hint: `${e.id} · ${e.caseId}`, media: e.media, run: () => go('investigate', { evidence: e.id }) })),
      ...findings.map(f => ({ id: f.id, group: 'Findings', label: f.title, hint: `${f.id} · ${branchLabel[f.branch]}`, icon: Film, run: () => go('investigate', { evidence: f.evidenceId, finding: f.id }) })),
    ];
    return [...actions, ...nav, ...more]
      .map(it => ({ it, sc: Math.max(score(q, it.label), score(q, `${it.hint ?? ''}`) * .8) }))
      .filter(x => x.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, 14).map(x => x.it);
  }, [q, page, ctx.caseId, ctx.evidenceId, go, onClose, toggleRail, cases, evidence, findings, router]);

  useEffect(() => { setSel(0); }, [q, page]);
  useEffect(() => { list.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: 'nearest' }); }, [sel]);

  const exec = (it?: Item) => { if (!it) return; it.run(); if (!it.stay) onClose(); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel(v => (v + 1) % Math.max(1, items.length)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(v => (v - 1 + items.length) % Math.max(1, items.length)); }
    else if (e.key === 'Enter') { e.preventDefault(); exec(items[sel]); }
    else if (e.key === 'Escape') { e.preventDefault(); if (page !== 'root') { setPage('root'); setQ(''); } else onClose(); }
    else if (e.key === 'Backspace' && !q && page !== 'root') setPage('root');
    else if (!q && page === 'root' && e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
      const hit = items.find(it => it.key?.toLowerCase() === e.key.toLowerCase());
      if (hit) { e.preventDefault(); exec(hit); }
    }
  };

  let lastGroup = '';
  return <AnimatePresence>{open && <>
    <motion.div className={s.scrim} onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} />
    <motion.div className={s.palette} role='dialog' aria-modal='true' aria-label='Command palette' initial={{ opacity: 0, y: -8, scale: .985 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: .99 }} transition={{ duration: .16, ease: [.22, 1, .36, 1] }}>
      <div className={s.palInput}>
        {page === 'cases' ? <button className={s.iconBtn} style={{ width: 28, height: 28 }} onClick={() => setPage('root')} aria-label='Back'><ArrowLeft size={15} /></button> : <Search size={18} />}
        {page === 'cases' && <span className={s.palChip}>Open investigation</span>}
        <input ref={input} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} placeholder={page === 'cases' ? 'Filter investigations' : 'Search evidence, cases, findings or run a command'} aria-label='Command' aria-activedescendant={`pal-${sel}`} role='combobox' aria-expanded='true' aria-controls='pal-list' />
        <kbd className={s.kbd}>Esc</kbd>
      </div>
      <div ref={list} className={s.palList} id='pal-list' role='listbox'>
        {items.length ? items.map((it, i) => {
          const head = it.group !== lastGroup ? (lastGroup = it.group) : null;
          const c = cases.find(x => x.id === it.id);
          return <div key={`${it.group}-${it.id}`}>
            {head && <p className={s.palGroup}>{head === 'Actions' && !q ? 'Available actions' : head}</p>}
            <button id={`pal-${i}`} data-i={i} role='option' aria-selected={i === sel} className={`${s.palItem} ${i === sel ? s.palOn : ''}`} onMouseMove={() => setSel(i)} onClick={() => exec(it)}>
              {it.media ? <Thumb media={it.media} sizes='30px' /> : it.icon && <it.icon size={17} />}
              <span>{it.label}</span>
              {c ? <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot> : it.hint && <small>{it.hint}</small>}
              {it.key && <kbd>{it.key}</kbd>}
            </button>
          </div>;
        }) : <p className={s.palEmpty}>Nothing matches “{q}”. Try a case ID, a file name or a command.</p>}
      </div>
      <div className={s.palFoot}><span><kbd>↑ ↓</kbd>Navigate</span><span><kbd>↵</kbd>Execute</span><span><kbd>Esc</kbd>{page === 'root' ? 'Close' : 'Back'}</span></div>
    </motion.div>
  </>}</AnimatePresence>;
}
