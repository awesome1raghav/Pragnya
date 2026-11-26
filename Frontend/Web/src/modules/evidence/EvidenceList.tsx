'use client';

/* /evidence: the evidence inventory across investigations, or within one (?case=). Filtering and
   search (filename, EVD number, SHA-256 prefix) run on the server. */
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Search, Upload } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { MEDIA_TYPES, type MediaType } from '@/api';
import { useCase, useEvidenceList, useEvidenceStatistics } from '@/api/hooks';
import CaseScope from '@/components/CaseScope';
import { Empty, Load, PageHead, Pager } from '@/components/ui';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';
import { bytes, mediaLabel } from '@/utils/labels';
import EvidenceRows from './EvidenceRows';

export default function EvidenceList() {
  const { caseId } = useCaseContext();
  const scoped = useCase(caseId);
  const [kind, setKind] = useState<MediaType | 'ALL'>('ALL');
  const [text, setText] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => { setSearch(text.trim()); setPage(1); }, 250); return () => clearTimeout(t); }, [text]);
  useEffect(() => { setPage(1); }, [kind, caseId]);
  const list = useEvidenceList({ case_id: caseId ?? undefined, media_type: kind === 'ALL' ? undefined : kind, search: search || undefined, page, page_size: 25 });
  const stats = useEvidenceStatistics();

  return <div className={s.page}>
    <PageHead title='Evidence' desc={caseId ? 'Preserved originals in this investigation. Open one to examine its bytes, metadata and custody.' : `Every preserved original${stats.data ? ` — ${stats.data.total_evidence} files, ${bytes(stats.data.total_bytes)}` : ''}. Open one to examine it.`}>
      {caseId && scoped.data && scoped.data.status !== 'ARCHIVED' && <Link className={`${s.btn} ${s.primary}`} href={paths.caseAddEvidence(caseId)}><Upload size={15} />Add evidence</Link>}
    </PageHead>
    <CaseScope />
    <div className={s.listBar}>
      <div className={s.seg} role='tablist' aria-label='Media type'>
        {(['ALL', ...MEDIA_TYPES] as const).map(k => <button key={k} role='tab' aria-selected={kind === k} onClick={() => setKind(k)}>{k === 'ALL' ? 'All' : mediaLabel[k]}{!caseId && stats.data && <span className={s.count}>{k === 'ALL' ? stats.data.total_evidence : stats.data.by_media_type[k]}</span>}</button>)}
      </div>
      <label className={`${s.cmdk} ${s.listSearch}`}><Search size={14} /><input value={text} onChange={e => setText(e.target.value)} placeholder='Filename, EVD-0001 or SHA-256 prefix' aria-label='Search evidence' /></label>
    </div>
    <Load q={list} rows={6}>{res => res.data.length ? <>
      <EvidenceRows items={res.data} showCase={!caseId} />
      <Pager page={res.pagination.page} pages={res.pagination.total_pages} total={res.pagination.total_items} onPage={setPage} />
    </> : <Empty title={search ? 'No evidence matches' : 'No evidence here yet'}>
      {search ? `Nothing matches “${search}”.` : caseId ? 'Add the original files this investigation needs to examine.' : 'Evidence is added inside an investigation: open one, then choose Add evidence.'}
    </Empty>}</Load>
  </div>;
}
