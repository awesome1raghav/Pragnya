'use client';

/* Global search and command palette (Ctrl/⌘ K). Commands are filtered locally; investigations and
   evidence come from the backend's /search, so results cover everything stored, not just what is on
   screen. The palette says which resource types it cannot search yet. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { FileSearch, FolderOpen, LoaderCircle, PanelLeft, Plus, Search, Upload, type LucideIcon } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { api, type ApiError, type SearchResults } from '@/api';
import { NAV } from '@/config/navigation';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';

type Item = { id: string; group: string; label: string; hint?: string; icon: LucideIcon; run: () => void };

function score(q: string, text: string) {
  if (!q) return 1;
  const t = text.toLowerCase(); let i = 0, sc = 0, run = 0;
  for (const ch of q.toLowerCase()) {
    const j = t.indexOf(ch, i); if (j < 0) return 0;
    run = j === i ? run + 1 : 0; sc += 1 + run * 2 + (j === 0 || t[j - 1] === ' ' ? 3 : 0); i = j + 1;
  }
  return sc / t.length;
}

export default function SearchPalette({ open, onClose, toggleRail }: { open: boolean; onClose: () => void; toggleRail: () => void }) {
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const [found, setFound] = useState<{ q: string; res?: SearchResults; err?: ApiError } | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { caseId } = useCaseContext();

  useEffect(() => { if (open) { setQ(''); setSel(0); setFound(null); requestAnimationFrame(() => input.current?.focus()); } }, [open]);

  // backend search, debounced; a newer query always wins
  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) { setFound(null); setBusy(false); return; }
    setBusy(true);
    let live = true;
    const t = setTimeout(() => {
      api.search(text).then(res => { if (live) setFound({ q: text, res }); }, err => { if (live) setFound({ q: text, err }); }).finally(() => { if (live) setBusy(false); });
    }, 220);
    return () => { live = false; clearTimeout(t); };
  }, [q]);

  const items = useMemo<Item[]>(() => {
    const go = (href: string) => () => router.push(href);
    const commands: Item[] = [
      { id: 'new', group: 'Actions', label: 'New investigation', icon: Plus, run: go(paths.newInvestigation()) },
      ...(caseId ? [{ id: 'add', group: 'Actions', label: 'Add evidence to the current investigation', icon: Upload, run: go(paths.caseAddEvidence(caseId)) }] : []),
      { id: 'cases', group: 'Actions', label: 'Open investigations', icon: FolderOpen, run: go(paths.investigations()) },
      { id: 'evidence', group: 'Actions', label: 'Browse evidence', icon: FileSearch, run: go(paths.evidenceList(caseId)) },
      ...NAV.map(n => ({ id: `nav-${n.href}`, group: 'Go to', label: n.label, icon: n.icon as LucideIcon, run: go(n.scoped && caseId ? `${n.href}?case=${encodeURIComponent(caseId)}` : n.href) })),
      { id: 'rail', group: 'Go to', label: 'Toggle sidebar', hint: 'Ctrl B', icon: PanelLeft, run: toggleRail },
    ];
    const text = q.trim();
    const filtered = text ? commands.map(it => ({ it, sc: score(text, it.label) })).filter(x => x.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, 6).map(x => x.it) : commands;
    const hits: Item[] = found?.res?.hits.map(h => ({
      id: `${h.type}-${h.id}`, group: h.type === 'CASE' ? 'Investigations' : 'Evidence', label: h.title, hint: h.subtitle,
      icon: h.type === 'CASE' ? FolderOpen : FileSearch, run: go(h.type === 'CASE' ? paths.case(h.id) : paths.evidence(h.id)),
    })) ?? [];
    const order = (g: string) => ({ Investigations: 0, Evidence: 1, Actions: 2, 'Go to': 3 } as Record<string, number>)[g] ?? 9;
    return [...hits, ...filtered].sort((a, b) => order(a.group) - order(b.group));
  }, [q, found, caseId, toggleRail, router]);

  useEffect(() => { setSel(0); }, [q, found]);
  useEffect(() => { list.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: 'nearest' }); }, [sel]);

  const exec = (it?: Item) => { if (!it) return; it.run(); onClose(); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel(v => (v + 1) % Math.max(1, items.length)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(v => (v - 1 + items.length) % Math.max(1, items.length)); }
    else if (e.key === 'Enter') { e.preventDefault(); exec(items[sel]); }
    else if (e.key === 'Escape') { e.preventDefault(); onClose(); }
  };

  let lastGroup = '';
  const text = q.trim();
  return <AnimatePresence>{open && <>
    <motion.div className={s.scrim} onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} />
    <motion.div className={s.palette} role='dialog' aria-modal='true' aria-label='Search and commands' initial={{ opacity: 0, y: -8, scale: .985 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: .99 }} transition={{ duration: .16, ease: [.22, 1, .36, 1] }}>
      <div className={s.palInput}>
        {busy ? <LoaderCircle size={18} className={s.spin} /> : <Search size={18} />}
        <input ref={input} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} placeholder='Search investigations and evidence, or run a command' aria-label='Search' role='combobox' aria-expanded='true' aria-controls='pal-list' aria-activedescendant={`pal-${sel}`} />
        <kbd className={s.kbd}>Esc</kbd>
      </div>
      <div ref={list} className={s.palList} id='pal-list' role='listbox'>
        {items.map((it, i) => {
          const head = it.group !== lastGroup ? (lastGroup = it.group) : null;
          return <div key={it.id}>
            {head && <p className={s.palGroup}>{head}</p>}
            <button id={`pal-${i}`} data-i={i} role='option' aria-selected={i === sel} className={`${s.palItem} ${i === sel ? s.palOn : ''}`} onMouseMove={() => setSel(i)} onClick={() => exec(it)}>
              <it.icon size={17} /><span>{it.label}</span>{it.hint && <small>{it.hint}</small>}
            </button>
          </div>;
        })}
        {text.length >= 2 && !busy && found?.res && found.res.hits.length === 0 && <p className={s.palEmpty}>No investigation or evidence matches “{text}”.</p>}
        {found?.err && <p className={s.palEmpty}>Search failed: {found.err.unreachable ? 'the API is unreachable' : found.err.message}</p>}
      </div>
      <div className={s.palFoot}>
        <span><kbd>↑ ↓</kbd>Navigate</span><span><kbd>↵</kbd>Open</span>
        <span style={{ marginLeft: 'auto' }}>{found?.res ? `Searches ${found.res.searched_types.map(t => t.toLowerCase()).join(' and ')}; ${found.res.not_searchable_yet.map(t => `${t.toLowerCase()}s`).join(', ')} are not searchable yet` : 'Type 2+ characters to search investigations and evidence'}</span>
      </div>
    </motion.div>
  </>}</AnimatePresence>;
}
