'use client';

/* Global job monitor (Flowchart B): a drawer that opens over any page, so watching work never means leaving it.
   Active work first, then what needs attention (failures never collapsed; routine partial runs grouped), then finished
   background work grouped by kind. From the Job API; live events keep it current. */
import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { useJobs } from '@/api/hooks';
import { Empty, Load, SecHead } from '@/components/ui';
import { GroupedJobList, JobList, WorkerNotice } from '@/modules/jobs/Jobs';
import jm from './jobMonitor.module.css';

export default function JobMonitor({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return <AnimatePresence>{open && <>
    <motion.div className={s.scrim} onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} />
    <motion.aside className={p.drawer} role='dialog' aria-modal='true' aria-label='Job monitor' initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
      <header className={p.drawerHead}><h2 className={s.title}>Job monitor</h2><button className={s.iconBtn} onClick={onClose} aria-label='Close job monitor'><X size={17} /></button></header>
      <div className={p.drawerBody}><JobBody /></div>
    </motion.aside>
  </>}</AnimatePresence>;
}

function JobBody() {
  const active = useJobs({ active: true, page_size: 50 });
  const partial = useJobs({ state: 'PARTIALLY_COMPLETED', page_size: 15 });
  const failed = useJobs({ state: 'FAILED', page_size: 15 });
  const recent = useJobs({ page_size: 30 });
  return <>
    <WorkerNotice />
    <section aria-label='Active jobs' className={jm.section}>
      <SecHead title='Active' count={active.data?.pagination.total_items} />
      <Load q={active} rows={2}>{r => r.data.length ? <JobList jobs={r.data} /> : <p className={s.cap}>Nothing queued or running.</p>}</Load>
    </section>
    <section aria-label='Jobs requiring attention' className={jm.section}>
      <SecHead title='Needs attention' count={(partial.data?.pagination.total_items ?? 0) + (failed.data?.pagination.total_items ?? 0)} />
      <Load q={partial} rows={1}>{pa => <Load q={failed} rows={1}>{f => {
        if (!pa.data.length && !f.data.length) return <p className={s.cap}>No failed or partial jobs.</p>;
        return <>
          {f.data.length > 0 && <JobList jobs={f.data} />}{/* failures are never collapsed */}
          {pa.data.length > 0 && <>
            <p className={jm.note}>Partial runs are usually expected: a module that does not apply, or a detector that is not installed. Retry after installing one.</p>
            <GroupedJobList jobs={pa.data} />
          </>}
        </>;
      }}</Load>}</Load>
    </section>
    <section aria-label='Recent jobs' className={jm.section}>
      <SecHead title='Recent' />
      <Load q={recent} rows={3}>{r => {
        const done = r.data.filter(j => j.state === 'COMPLETED' || j.state === 'CANCELLED');
        return done.length ? <GroupedJobList jobs={done} /> : <Empty title='No finished jobs yet'>Uploading evidence queues an investigation run for it.</Empty>;
      }}</Load>
    </section>
  </>;
}
