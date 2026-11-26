'use client';

/* /evidence (every file across cases), the workbench route wrapper, and /evidence/:id/integrity. */
import Link from 'next/link';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ArrowRight, Search, ShieldCheck } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/demo/stores/workspace.store';
import { mb, statusLabel } from '@/demo/utils/labels';
import { Dot, PageHead, fmt, type Ctx } from '@/demo/components/ui';
import { paths, toolFromSegment } from '@/demo/config/routes';
import { EvidenceGrid } from '@/demo/modules/investigations/CasePages';
import { useWorkspace } from '@/demo/layouts/MainLayout';
import Workbench from './Workbench';

const KINDS = ['all', 'video', 'image', 'audio'] as const;

export function EvidenceList() {
  const { evidence, cases } = useData();
  const [kind, setKind] = useState<(typeof KINDS)[number]>('all');
  const [q, setQ] = useState('');
  const list = useMemo(() => evidence.filter(e => (kind === 'all' || e.kind === kind) && `${e.fileName} ${e.id} ${e.source}`.toLowerCase().includes(q.toLowerCase())), [evidence, kind, q]);
  return <div className={s.page}>
    <PageHead title='Evidence' desc={`${evidence.length} preserved files across ${cases.length} investigations.`} />
    <div className={s.listBar}>
      <div className={s.seg} role='tablist' aria-label='Media type'>{KINDS.map(k => <button key={k} role='tab' aria-selected={kind === k} onClick={() => setKind(k)}>{k === 'all' ? 'All' : k[0].toUpperCase() + k.slice(1)}<span className={s.count}>{k === 'all' ? evidence.length : evidence.filter(e => e.kind === k).length}</span></button>)}</div>
      <label className={`${s.cmdk} ${s.listSearch}`}><Search size={14} /><input value={q} onChange={e => setQ(e.target.value)} placeholder='Find a file, ID or source' aria-label='Find evidence' /></label>
    </div>
    {list.length ? <EvidenceGrid items={list} /> : <div className={s.empty}><b>No evidence matches</b><span>Try another name, ID or source.</span></div>}
  </div>;
}

/* The workbench lives in the /evidence/:id layout, so moving between its tools (which are addresses) keeps
   it mounted. The selected finding and a requested analysis run travel in the query string. */
export function WorkbenchRoute({ children }: { children: ReactNode }) {
  const ctx = useWorkspace();
  const pathname = usePathname();
  const sp = useSearchParams();
  const router = useRouter();
  const seg = pathname.split('/')[3];
  const runId = Number(sp.get('run')) || 0;
  const withQuery = (base: string, patch: Record<string, string | null>) => {
    const n = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) v ? n.set(k, v) : n.delete(k);
    return n.size ? `${base}?${n}` : base;
  };
  useEffect(() => { if (runId) router.replace(withQuery(pathname, { run: null }), { scroll: false }); }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (seg === 'integrity') return <>{children}</>;
  return <>
    <Workbench {...ctx} tool={toolFromSegment(seg)} runId={runId} finding={sp.get('finding')}
      setTool={t => router.replace(withQuery(paths.evidence(ctx.evidenceId, t), { run: null }), { scroll: false })}
      setFinding={f => router.replace(withQuery(pathname, { finding: f, run: null }), { scroll: false })} />
    {children}
  </>;
}

/* ── /evidence/:id/integrity ── */
export function Integrity({ evidenceId }: Ctx) {
  const { evidence, cases, audit } = useData();
  const e = evidence.find(x => x.id === evidenceId)!;
  const c = cases.find(x => x.id === e.caseId);
  const trail = audit.filter(a => a.text.includes(e.id));
  return <div className={s.page}>
    <PageHead title='Integrity' desc={<>How <span className={s.mono}>{e.fileName}</span> has been preserved since it arrived.</>}>
      <Link className={`${s.btn} ${s.ghost}`} href={paths.evidence(e.id)}>Open in workbench <ArrowRight size={15} /></Link>
    </PageHead>
    <div className={s.intGrid}>
      <section className={s.panel}>
        <p className={s.title}><ShieldCheck size={16} style={{ color: 'var(--ok)', verticalAlign: -3, marginRight: 8 }} />Sealed original</p>
        <div><p className={s.cap}>SHA-256 recorded at intake</p><code className={s.hash}>{e.sha256}</code></div>
        <dl className={s.kv}>
          <div><dt>Investigation</dt><dd>{c ? <Link href={paths.case(c.id)}>{c.name}</Link> : e.caseId}</dd></div>
          <div><dt>Status</dt><dd><Dot tone='mute'>{statusLabel[e.status]}</Dot></dd></div>
          <div><dt>Size</dt><dd>{mb(e.sizeBytes)}</dd></div>
          <div><dt>Format</dt><dd>{e.codec} · {e.width} × {e.height}{e.kind === 'video' ? ` · ${fmt(e.durationSec)}` : ''}</dd></div>
          <div><dt>Source</dt><dd>{e.source}</dd></div>
          <div><dt>Captured</dt><dd>{e.capturedAt.replace('T', ' ').replace('Z', ' UTC')}</dd></div>
          <div><dt>Storage</dt><dd>Read-only; analysis works on copies</dd></div>
        </dl>
      </section>
      <section className={s.ledger} aria-label='Custody trail'>
        <header className={s.ledgerHead}><p className={s.title}>Custody trail <span className={s.muted} style={{ fontWeight: 400 }}>{trail.length} signed events</span></p></header>
        {trail.length ? trail.map(a => <div key={a.seq} className={s.eventWrap}><div className={s.event}><i style={{ background: a.verified ? 'var(--ok)' : 'var(--alert)' }} /><span className={s.eventMain}><b>{a.text}</b><small>{a.at.slice(0, 16).replace('T', ' ')} UTC · {a.actor}</small></span><Dot tone={a.verified ? 'ok' : 'alert'}>{a.verified ? 'Verified' : 'Revoked'}</Dot></div></div>)
          : <p className={s.cap} style={{ padding: 14 }}>No access has been recorded for this file since intake.</p>}
      </section>
    </div>
  </div>;
}
