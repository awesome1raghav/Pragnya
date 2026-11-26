'use client';

/* /reports: one report per investigation, with where it stands. */
import Link from 'next/link';
import { ArrowRight, Eye } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/demo/stores/workspace.store';
import { timeOf } from '@/demo/utils/labels';
import { Dot, PageHead, Thumb } from '@/demo/components/ui';
import { paths } from '@/demo/config/routes';

export default function ReportList() {
  const { cases, evidence, findings, decisions } = useData();
  return <div className={s.page}>
    <PageHead title='Reports' desc='One forensic report per investigation. Each claim cites its source and states its confidence.' />
    <ul className={s.list}>{[...cases].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).map((c, i) => {
      const ev = evidence.filter(e => e.caseId === c.id);
      const fs = findings.filter(f => ev.some(e => e.id === f.evidenceId) && f.status !== 'rejected');
      const awaiting = decisions.some(d => d.caseId === c.id && d.kind === 'approve_report');
      const state = c.status === 'verified' ? ['Final', 'ok'] : awaiting ? ['Awaiting approval', 'gold'] : ['Draft', 'mute'];
      return <li key={c.id} className={s.listRowWrap}>
        <Link className={s.listRow} href={paths.report(c.id)}>
          <Thumb media={c.cover} sizes='80px' eager={i < 6} />
          <span className={s.listMain}><b>{c.name}</b><small><span className={s.mono}>{c.id}</span> · {fs.length} findings · {ev.length} sources</small></span>
          <Dot tone={state[1] as 'ok' | 'gold' | 'mute'}>{state[0]}</Dot>
          <time className={s.listTime}>{timeOf(c.updatedAt)}</time>
          <ArrowRight size={15} className={s.rowChev} />
        </Link>
        <Link className={`${s.btn} ${s.sm} ${s.ghost} ${s.listAside}`} href={paths.reportPreview(c.id)}><Eye size={14} />Preview</Link>
      </li>;
    })}</ul>
  </div>;
}
