'use client';

/* /intelligence: the 18 investigation modules in their five groups, the canonical connectivity between
   them, and T-MIR's coordination boundary, all from GET /system/modules. Selecting a module shows its
   upstream and downstream edges, what it does today and its API, and, for the investigation in scope, what that
   module did in the latest T-MIR run (state and reason per scope, from the stored plan). */
import Link from 'next/link';
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import ix from './intelligence.module.css';
import { motion } from 'framer-motion';
import type { ModuleCatalogue, ModuleEdge, ModuleInfo } from '@/api';
import { useCaseRuns, useJobs, useModules, useRun } from '@/api/hooks';
import { useCaseContext } from '@/state/CaseContext';
import { PlanTable } from '@/modules/jobs/Jobs';
import CaseScope from '@/components/CaseScope';
import { Dot, Empty, Load, PageHead, SecHead } from '@/components/ui';
import { moduleStatusLabel, moduleStatusTone } from '@/utils/labels';

const EXEC: Record<ModuleInfo['executed_by'], string> = {
  DOMAIN_SERVICE: 'Domain service, in the request', 'T-MIR': 'Coordinated by T-MIR', SOURCE_JOB: 'Source Service job', HUMAN_REVIEW: 'Human review', REPORT_JOB: 'Report Service job',
};

export default function Intelligence() {
  const q = useModules();
  return <div className={s.page}>
    <PageHead title='Intelligence' desc='The investigation modules, how data flows between them, and what each can do in this build. Select a module to trace it.' />
    <CaseScope />
    <Load q={q} rows={6}>{cat => <Catalogue cat={cat} />}</Load>
  </div>;
}

function Catalogue({ cat }: { cat: ModuleCatalogue }) {
  const [sel, setSel] = useState<string | null>('NEX-EVD');
  const byId = useMemo(() => new Map(cat.modules.map(m => [m.module_id, m])), [cat]);
  const counts = (st: string) => cat.modules.filter(m => m.status === st).length;
  const selected = sel ? byId.get(sel) : undefined;
  const related = useMemo(() => new Set(selected ? [selected.module_id, ...selected.upstream, ...selected.downstream] : []), [selected]);

  return <>
    <motion.p className={ix.summary} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: .2 }}>
      <b>{cat.modules.length}</b> modules: <Dot tone='ok'>{counts('IMPLEMENTED')} implemented</Dot> <Dot tone='gold'>{counts('PARTIAL')} partial</Dot>
      {counts('NOT_IMPLEMENTED') > 0 && <Dot tone='mute'>{counts('NOT_IMPLEMENTED')} not built yet</Dot>}
      <span className={ix.sep}>·</span> T-MIR {moduleStatusLabel[cat.tmir.status].toLowerCase()}, coordinating {cat.tmir.coordinates.length}
    </motion.p>
    <section className={s.panel} aria-label='Module dependency map'>
      <SecHead title='Module connectivity'><span className={s.cap}>{cat.source}</span></SecHead>
      <ModuleMap cat={cat} sel={sel} onSel={setSel} related={related} />
      <div className={p.legend}><Dot tone='ok'>Implemented</Dot><Dot tone='gold'>Partial</Dot><Dot tone='mute'>Not built yet</Dot><span><span className={s.mono}>T-MIR</span> marks the modules T-MIR coordinates</span><span>Select a module to trace its dependencies</span></div>
    </section>
    <div className={p.grid2} style={{ marginTop: 20 }}>
      {selected ? <ModuleDetail m={selected} byId={byId} onSel={setSel} tmir={cat.tmir.coordinates.includes(selected.module_id)} edges={cat.edges} /> : <section className={s.panel}><p className={s.cap}>Select a module above.</p></section>}
      <Executions moduleId={selected?.module_id ?? null} tmir={!!selected && cat.tmir.coordinates.includes(selected.module_id)} />
    </div>
  </>;
}

function ModuleMap({ cat, sel, onSel, related }: { cat: ModuleCatalogue; sel: string | null; onSel: (id: string | null) => void; related: Set<string> }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [boxes, setBoxes] = useState<Record<string, DOMRect>>({});
  const [origin, setOrigin] = useState<DOMRect | null>(null);

  useLayoutEffect(() => {
    const el = wrap.current; if (!el) return;
    const measure = () => {
      const o = el.getBoundingClientRect(); setOrigin(o);
      const next: Record<string, DOMRect> = {};
      el.querySelectorAll<HTMLElement>('[data-mod]').forEach(n => { next[n.dataset.mod!] = n.getBoundingClientRect(); });
      setBoxes(next);
    };
    measure();
    const ro = new ResizeObserver(measure); ro.observe(el);
    return () => ro.disconnect();
  }, [cat]);

  const edges = cat.modules.flatMap(m => m.upstream.map(u => [u, m.module_id] as const));
  return <div className={p.mapWrap}><div className={p.map} ref={wrap}>
    {origin && <svg width='100%' height='100%' aria-hidden='true'>
      {edges.map(([a, b]) => {
        const A = boxes[a], B = boxes[b]; if (!A || !B) return null;
        const sameCol = Math.abs(A.left - B.left) < 4;
        const x1 = (sameCol ? A.left + A.width * .5 : A.right) - origin.left, y1 = (sameCol ? A.bottom : A.top + A.height / 2) - origin.top;
        const x2 = (sameCol ? B.left + B.width * .5 : B.left) - origin.left, y2 = (sameCol ? B.top : B.top + B.height / 2) - origin.top;
        const d = sameCol ? `M${x1},${y1} L${x2},${y2}` : `M${x1},${y1} C${x1 + 28},${y1} ${x2 - 28},${y2} ${x2},${y2}`;
        return <path key={`${a}-${b}`} d={d} className={p.edge} data-on={!!sel && (a === sel || b === sel)} />;
      })}
    </svg>}
    <div className={p.mapCols}>{cat.groups.map(g => <div key={g} className={p.mapCol}>
      <p>{g}</p>
      {cat.modules.filter(m => m.group === g).map(m => <button key={m.module_id} data-mod={m.module_id} className={p.mod} data-status={m.status}
        data-sel={sel === m.module_id} data-dim={!!sel && !related.has(m.module_id)} data-tmir={cat.tmir.coordinates.includes(m.module_id)}
        onClick={() => onSel(sel === m.module_id ? null : m.module_id)} aria-pressed={sel === m.module_id}>
        <b>{String(m.number).padStart(2, '0')} {m.module_id}</b><span>{m.name}</span>
        <small><Dot tone={moduleStatusTone[m.status]}>{moduleStatusLabel[m.status]}</Dot></small>
      </button>)}
    </div>)}</div>
  </div></div>;
}

function ModuleDetail({ m, byId, onSel, tmir, edges }: { m: ModuleInfo; byId: Map<string, ModuleInfo>; onSel: (id: string) => void; tmir: boolean; edges: ModuleEdge[] }) {
  const edgeOf = (a: string, b: string) => edges.find(e => e.upstream === a && e.downstream === b);
  const chip = (id: string, e?: ModuleEdge) => <button key={id} onClick={() => onSel(id)} title={e ? `${e.kind.toLowerCase()}: ${e.reason}` : byId.get(id)?.name}>{id}{e ? ` · ${e.kind.toLowerCase()}` : ''}</button>;
  return <section className={`${s.panel} ${p.detail}`} aria-label={`${m.module_id} detail`}>
    <SecHead title={<>{m.module_id} · {m.name}</>}><Dot tone={moduleStatusTone[m.status]}>{moduleStatusLabel[m.status]}</Dot></SecHead>
    <dl className={s.kv}>
      <div><dt>Group</dt><dd>{m.group}</dd></div>
      <div><dt>Runs as</dt><dd>{EXEC[m.executed_by]}{tmir ? '' : m.executed_by === 'DOMAIN_SERVICE' ? ' (not T-MIR)' : ''}</dd></div>
    </dl>
    <div><p className={s.cap}>Receives data from</p><div className={p.chips} style={{ marginTop: 6 }}>{m.upstream.length ? m.upstream.map(u => chip(u, edgeOf(u, m.module_id))) : <span>{m.module_id === 'NEX-SRC' ? 'Entry not defined in the flowchart: investigator-supplied source URLs (plan decision D-13)' : 'Investigation entry'}</span>}</div></div>
    <div><p className={s.cap}>Feeds</p><div className={p.chips} style={{ marginTop: 6 }}>{m.downstream.length ? m.downstream.map(d => chip(d, edgeOf(m.module_id, d))) : <span>Final output</span>}</div></div>
    {m.capabilities.length > 0 && <div><p className={s.cap}>Works today</p><ul className={s.miniList}>{m.capabilities.map(c => <li key={c}><small>{c}</small></li>)}</ul></div>}
    {m.endpoints.length > 0 && <div><p className={s.cap}>API</p><div className={p.chips} style={{ marginTop: 6 }}>{m.endpoints.map(e => <span key={e}>{e}</span>)}</div></div>}
    {m.note && <p className={p.warnLine}>{m.note}</p>}
    {m.status === 'NOT_IMPLEMENTED' && <p className={s.cap}>Not built yet. See the plan in Documentation/Implementation for when it lands.</p>}
    {m.module_id === 'NEX-EVD' && <Link className={s.secLink} href='/evidence'>Open the evidence inventory</Link>}
  </section>;
}

/* What the selected module did in the latest run of the investigation in scope (or the latest run anywhere). */
function Executions({ moduleId, tmir }: { moduleId: string | null; tmir: boolean }) {
  const { caseId } = useCaseContext();
  const caseRuns = useCaseRuns(caseId);
  const anyRuns = useJobs({ job_type: 'INVESTIGATION_RUN', page_size: 1 });
  const latest = (caseId ? caseRuns.data?.data[0] : anyRuns.data?.data[0]) ?? null;
  const run = useRun(latest?.job_id ?? null);
  return <section className={s.panel} aria-label='Execution status'>
    <SecHead title={moduleId ? `${moduleId} in the latest run` : 'Latest run'}>{latest && <span className={s.cap}>{latest.job_number}{latest.case_number ? ` · ${latest.case_number}` : ''}</span>}</SecHead>
    {!tmir ? <p className={s.cap}>{moduleId ? `${moduleId} is not coordinated by T-MIR, so it has no executions in investigation runs.` : 'Select a module.'}</p>
      : !latest ? <Empty title='No runs yet'>{caseId ? 'This investigation has no T-MIR run yet.' : 'No investigation has been analysed yet.'}</Empty>
      : <Load q={run} rows={3}>{r => {
        const rows = r.plan.filter(e => e.module_id === moduleId);
        return rows.length ? <PlanTable plan={rows} scopeLabel={e => (e.scope_kind === 'EVIDENCE' ? `evidence ${e.scope_ref.slice(0, 8)}…` : e.scope_kind.toLowerCase())} /> : <p className={s.cap}>{r.plan.length ? 'Not part of this run.' : 'The run has not been planned yet.'}</p>;
      }}</Load>}
  </section>;
}
