'use client';

/* Level 4 of the viewer: the full execution record for this evidence item (every module with its state, reason, tool
   versions and time; the runs that included it; the case-level modules of the latest run). Collapsed by default. */
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import type { Evidence, EvidenceAnalysis } from '@/api';
import { SecHead } from '@/components/ui';
import { LatestRunCaseModules, ModuleTable } from '@/modules/analysis/Analysis';
import { JobList, WorkerNotice } from '@/modules/jobs/Jobs';
import v from './viewer.module.css';

export function ExecutionRecord({ a, ev }: { a: EvidenceAnalysis; ev: Evidence }) {
  const [open, setOpen] = useState(false);
  return <section className={v.record} aria-label='Execution record'>
    <button className={v.recordHead} onClick={() => setOpen(x => !x)} aria-expanded={open}>
      <ChevronDown size={15} style={{ transform: open ? undefined : 'rotate(-90deg)', transition: 'transform .2s' }} />
      <b>Execution record</b><small>{a.modules.filter(m => m.latest).length} modules · {a.jobs.length} run{a.jobs.length === 1 ? '' : 's'} · tool versions, states and reasons</small>
    </button>
    {open && <div className={v.recordBody}>
      <WorkerNotice quietWhenAlive />
      <section className={s.panel} aria-label='Modules for this evidence'>
        <SecHead title='Modules' />
        <ModuleTable a={a} />
      </section>
      <section className={s.panel} aria-label='Runs for this evidence'>
        <SecHead title='Runs' count={a.jobs.length} />
        {a.jobs.length ? <JobList jobs={a.jobs} /> : <p className={s.cap}>No run has included {ev.evidence_number}.</p>}
      </section>
      {a.latest_job && <LatestRunCaseModules jobId={a.latest_job.job_id} />}
    </div>}
  </section>;
}
