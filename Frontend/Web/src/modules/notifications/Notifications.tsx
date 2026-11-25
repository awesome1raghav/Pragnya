'use client';

/* /notifications: what needs you first, then what happened. */
import Link from 'next/link';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import { severityTone, timeOf, toneColor } from '@/utils/labels';
import { Dot, FindingMark, PageHead, type Ctx } from '@/components/ui';
import { paths } from '@/config/routes';

export default function Notifications(_: Ctx) {
  const { decisions, activity, findings, cases } = useData();
  const name = (id: string) => cases.find(c => c.id === id)?.name ?? id;
  return <div className={s.page}>
    <PageHead title='Notifications' desc='Decisions waiting on you, then everything that changed in your investigations.' />
    <section className={s.block}>
      <header className={s.secHead}><h2 className={s.title}>Needs your decision <span className={s.muted}>{decisions.length}</span></h2></header>
      {decisions.length ? <ul className={s.list}>{decisions.map(d => {
        const f = findings.find(x => x.id === d.findingId);
        const href = f ? `${paths.evidence(f.evidenceId)}?finding=${encodeURIComponent(f.id)}` : d.kind === 'approve_report' ? paths.caseReport(d.caseId) : paths.caseReview(d.caseId);
        return <li key={d.id}><Link className={s.noteRow} href={href}>
          <span className={s.listMain}>{f && <FindingMark f={f} />}<b>{d.title}</b><small>{name(d.caseId)} · {d.rationale}</small></span>
          <Dot tone={severityTone[d.severity]}>{d.kind === 'approve_report' ? 'Report' : d.kind === 'resolve_conflict' ? 'Conflict' : 'Finding'}</Dot>
          <ArrowRight size={15} className={s.rowChev} />
        </Link></li>;
      })}</ul> : <div className={s.empty}><ShieldCheck size={24} /><b>Nothing waiting</b></div>}
    </section>
    <section className={s.block}>
      <header className={s.secHead}><h2 className={s.title}>Activity</h2></header>
      <ol className={s.feed} style={{ padding: 0 }}>{activity.map(a => <li key={a.id} style={{ color: toneColor[({ finding: 'alert', status: 'steel', integrity: 'ok', analysis: 'mute' } as const)[a.kind]] }}><time>{timeOf(a.at)}</time><p><Link href={paths.case(a.caseId)}>{a.text}</Link><small>{name(a.caseId)} · {a.actor}</small></p></li>)}</ol>
    </section>
  </div>;
}
