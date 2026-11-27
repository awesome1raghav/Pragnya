'use client';

/* Where an investigation stands: evidence → analysis → review → report, from /investigation-progress (stored records:
   evidence count, runs, the case-conclusion review, generated reports). The current stage is named with its next
   action; finished stages are marked, never animated as if work were happening. */
import Link from 'next/link';
import { ArrowRight, Check } from 'lucide-react';
import type { Progress } from '@/api';
import { paths } from '@/config/routes';
import st from './stages.module.css';

const STAGES: { id: Exclude<Progress['stage'], 'DONE'>; label: string }[] = [
  { id: 'ACQUIRE', label: 'Evidence' }, { id: 'ANALYSE', label: 'Analysis' }, { id: 'REVIEW', label: 'Review' }, { id: 'REPORT', label: 'Report' },
];
const index = (stage: Progress['stage']) => (stage === 'DONE' ? STAGES.length : STAGES.findIndex(x => x.id === stage));

const actionHref = (p: Progress) => ({
  ACQUIRE: paths.caseAddEvidence(p.case_id), ANALYSE: paths.caseAnalysis(p.case_id), REVIEW: paths.caseReview(p.case_id),
  REPORT: paths.caseReport(p.case_id), DONE: paths.caseReport(p.case_id),
}[p.stage]);

export function StageTrack({ progress, compact = false }: { progress: Progress; compact?: boolean }) {
  const at = index(progress.stage);
  const detail: Record<string, string> = {
    ACQUIRE: progress.evidence ? `${progress.evidence} item${progress.evidence === 1 ? '' : 's'}` : 'none yet',
    ANALYSE: progress.runs_active ? `${progress.runs_active} running` : progress.last_run_state ? progress.last_run_state.replace(/_/g, ' ').toLowerCase() : 'not run',
    REVIEW: progress.conclusion ? progress.conclusion.replace(/_/g, ' ').toLowerCase() : `${progress.inferences} inference${progress.inferences === 1 ? '' : 's'}`,
    REPORT: progress.final_report ? 'final' : progress.reports ? `${progress.reports} draft${progress.reports === 1 ? '' : 's'}` : 'none',
  };
  return <div className={compact ? st.compact : st.full}>
    <ol className={st.track} aria-label={`Investigation stage: ${progress.next_action}`}>
      {STAGES.map((x, k) => <li key={x.id} data-state={k < at ? 'done' : k === at ? 'now' : 'next'}>
        <i aria-hidden='true'>{k < at ? <Check size={11} strokeWidth={3} /> : null}</i>
        <span>{x.label}{!compact && <small>{detail[x.id]}</small>}</span>
      </li>)}
    </ol>
    {compact ? <span className={st.next}>{progress.next_action}<ArrowRight size={13} aria-hidden='true' /></span>
      : <Link href={actionHref(progress)} className={st.action}>{progress.next_action}<ArrowRight size={14} aria-hidden='true' /></Link>}
  </div>;
}
