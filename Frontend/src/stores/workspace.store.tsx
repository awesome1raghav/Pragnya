'use client';

/* Workspace data store. Loads everything a session needs in parallel through `api`, keeps it in one place,
   and exposes the mutations as actions that update the store optimistically. Views never call `api` directly
   except through these actions, so swapping mock for the real backend changes nothing in the UI. */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, type ActivityItem, type AnalysisJob, type AuditEvent, type Case, type Decision, type DecisionAction, type Evidence, type Finding, type FindingStatus, type Graph, type ModelInfo } from '@/api';

export type Snapshot = { cases: Case[]; evidence: Evidence[]; findings: Finding[]; graph: Graph; decisions: Decision[]; activity: ActivityItem[]; audit: AuditEvent[]; models: ModelInfo[] };
type Store = Snapshot & {
  status: 'loading' | 'ready' | 'error'; error?: string; reload: () => void;
  decide: (id: string, action: DecisionAction) => Promise<void>; restoreDecision: (d: Decision) => void;
  setFindingStatus: (id: string, status: FindingStatus) => Promise<void>;
  addEvidence: (e: Evidence) => void;
};
const EMPTY: Snapshot = { cases: [], evidence: [], findings: [], graph: { nodes: [], edges: [] }, decisions: [], activity: [], audit: [], models: [] };
const Ctx = createContext<Store | null>(null);

export function WorkspaceData({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Snapshot>(EMPTY);
  const [status, setStatus] = useState<Store['status']>('loading');
  const [error, setError] = useState<string>();

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const [cases, evidence, findings, graph, decisions, activity, audit, models] = await Promise.all([api.listCases(), api.listEvidence(), api.listFindings(), api.getGraph(), api.listDecisions(), api.listActivity(), api.listAudit(), api.listModels()]);
      setData({ cases, evidence, findings, graph, decisions, activity, audit, models }); setStatus('ready');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setStatus('error'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const decide = useCallback(async (id: string, action: DecisionAction) => {
    const d = data.decisions.find(x => x.id === id);
    setData(v => ({ ...v, decisions: v.decisions.filter(x => x.id !== id), findings: d?.findingId && (action === 'accept' || action === 'resolve') ? v.findings.map(f => f.id === d.findingId ? { ...f, status: 'accepted' } : f) : v.findings }));
    try { await api.decide(id, action); } catch { setData(v => ({ ...v, decisions: d ? [d, ...v.decisions] : v.decisions })); }
  }, [data.decisions]);
  const restoreDecision = useCallback((d: Decision) => setData(v => v.decisions.some(x => x.id === d.id) ? v : { ...v, decisions: [...v.decisions, d].sort((a, b) => a.id.localeCompare(b.id)) }), []);
  const setFindingStatus = useCallback(async (id: string, s: FindingStatus) => {
    setData(v => ({ ...v, findings: v.findings.map(f => f.id === id ? { ...f, status: s } : f) }));
    await api.updateFinding(id, s).catch(() => {});
  }, []);
  const addEvidence = useCallback((e: Evidence) => setData(v => ({ ...v, evidence: [...v.evidence, e] })), []);

  return <Ctx.Provider value={{ ...data, status, error, reload: load, decide, restoreDecision, setFindingStatus, addEvidence }}>{children}</Ctx.Provider>;
}

export function useData() {
  const v = useContext(Ctx); if (!v) throw new Error('useData outside WorkspaceData'); return v;
}

/* An analysis run: start it, poll until done, hand back live stages and, at the end, fresh findings. */
export function useAnalysis(onDone: (findings: Finding[]) => void) {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const alive = useRef(0);
  const run = useCallback(async (evidenceId: string) => {
    const my = ++alive.current;
    let j = await api.startAnalysis(evidenceId); setJob(j);
    while (alive.current === my && (j.state === 'queued' || j.state === 'running')) {
      await new Promise(r => setTimeout(r, 250));
      j = await api.getAnalysis(j.id); if (alive.current === my) setJob(j);
    }
    if (alive.current === my && j.state === 'done') { onDone(j.findings ?? []); setTimeout(() => alive.current === my && setJob(null), 250); }
  }, [onDone]);
  useEffect(() => () => { alive.current++; }, []);
  return { job, run, running: !!job && job.state !== 'failed' };
}
