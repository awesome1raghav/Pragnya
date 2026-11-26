'use client';

/* The investigation scope of a global page (Evidence, Sources, Lineage, Intelligence, Graph, Reports).
   The scope lives in the address (?case=). The last investigation you opened is offered, not applied. */
import Link from 'next/link';
import { X } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { useCase, useCases } from '@/api/hooks';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';

export default function CaseScope({ allLabel = 'All investigations' }: { allLabel?: string }) {
  const { caseId, from, lastCaseId, setScope } = useCaseContext();
  const current = useCase(caseId);
  const last = useCase(!caseId && lastCaseId ? lastCaseId : null);
  const options = useCases({ page_size: 100, sort_by: 'last_activity_at', sort_order: 'desc' });

  return <div className={p.scopeBar} role='group' aria-label='Investigation scope'>
    <span>Scope</span>
    {caseId ? <>
      <b>{current.data ? <Link href={paths.case(caseId)}>{current.data.case_number} · {current.data.title}</Link> : current.error ? <span style={{ color: 'var(--alert)' }}>Unknown investigation</span> : '…'}</b>
      {from !== 'record' && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => setScope(null)}><X size={14} />Show {allLabel.toLowerCase()}</button>}
    </> : <>
      <b>{allLabel}</b>
      <select className={s.input} value='' onChange={e => e.target.value && setScope(e.target.value)} aria-label='Limit to one investigation' disabled={!options.data}>
        <option value=''>{options.error ? 'Investigations unavailable' : options.data ? 'Limit to one investigation…' : 'Loading investigations…'}</option>
        {options.data?.data.map(c => <option key={c.case_id} value={c.case_id}>{c.case_number} · {c.title}</option>)}
      </select>
      {last.data && <span className={p.suggest}>Last opened: <button onClick={() => setScope(last.data!.case_id)}>{last.data.case_number} · {last.data.title}</button></span>}
    </>}
  </div>;
}
