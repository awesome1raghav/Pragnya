'use client';

import { useState } from 'react';
import { Download, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/demo/stores/workspace.store';
import type { AuditEvent } from '@/demo/api';
import { Dot, PageHead, type Ctx } from '@/demo/components/ui';

/* ── Governance and audit ── */
const KIND_LABEL: Record<AuditEvent['kind'], string> = { evidence_access: 'Evidence access', analysis: 'Analysis', model_change: 'Model change', access_control: 'Access control', export: 'Export', retention: 'Retention' };
const KINDS = Object.keys(KIND_LABEL) as AuditEvent['kind'][];

export function Audit({ notify, section = 'all' }: Ctx & { section?: 'all' | 'health' | 'logs' }) {
  const { audit, models } = useData();
  const [on, setOn] = useState<Set<string>>(new Set(KINDS));
  const [filters, setFilters] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const rows = audit.filter(e => on.has(e.kind));
  const filtered = on.size < KINDS.length;
  // the ledger as shown (current filters), as a CSV file
  const exportLog = () => {
    const cell = (v: string | number | boolean) => `"${String(v).replace(/"/g, '""')}"`;
    const csv = [['seq', 'at', 'kind', 'actor', 'text', 'signature', 'verified'], ...rows.map(e => [e.seq, e.at, e.kind, e.actor, e.text, e.signature, e.verified])].map(r => r.map(cell).join(',')).join('\r\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = `nextron-audit-${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    notify(`Downloaded ${rows.length} events as CSV`);
  };
  const filterList = KINDS.map(k => <label key={k} className={s.check}><input type='checkbox' checked={on.has(k)} onChange={() => setOn(v => { const n = new Set(v); if (n.has(k)) n.delete(k); else n.add(k); return n; })} />{KIND_LABEL[k]}<b className={s.muted}>{audit.filter(e => e.kind === k).length}</b></label>);

  return <div className={s.page}>
    <PageHead title={section === 'health' ? 'System health' : section === 'logs' ? 'Audit log' : 'Governance and audit'} desc={section === 'health' ? 'Chain of custody, signatures and the models allowed to produce findings.' : 'An append-only, signed record of who touched which evidence and when, and which models may produce findings.'} />
    {section !== 'health' && <div className={s.audit} data-section={section}>
      <section className={`${s.panel} ${s.filterPanel}`} aria-label='Event types'>
        <p className={s.title}>Event types</p>
        {filterList}
      </section>
      <section className={s.ledger} aria-label='Ledger'>
        <header className={s.ledgerHead}>
          <p className={s.title}>Ledger <span className={s.muted} style={{ fontWeight: 400 }}>{rows.length} events{filtered && ` · ${on.size} of ${KINDS.length} types`}</span></p>
          {filtered && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => setOn(new Set(KINDS))}>Clear filters</button>}
          <button className={`${s.btn} ${s.sm} ${s.ghost} ${s.filterBtn}`} aria-expanded={filters} onClick={() => setFilters(v => !v)}><SlidersHorizontal size={14} />Filters</button>
          <button className={`${s.btn} ${s.sm}`} onClick={exportLog}><Download size={14} />Export log</button>
        </header>
        {filters && <div className={s.filterSheet}>{filterList}</div>}
        {rows.length ? rows.map(e => <div key={e.seq} className={s.eventWrap}>
          <button className={s.event} aria-expanded={open === e.seq} onClick={() => setOpen(open === e.seq ? null : e.seq)}>
            <i style={{ background: e.verified ? 'var(--ok)' : 'var(--alert)' }} />
            <span className={s.eventMain}><b>{e.text}</b><small>{e.at.slice(0, 16).replace('T', ' ')} UTC · {KIND_LABEL[e.kind]} · {e.actor}</small></span>
            <Dot tone={e.verified ? 'ok' : 'alert'}>{e.verified ? 'Verified' : 'Revoked'}</Dot>
          </button>
          {open === e.seq && <dl className={`${s.kv} ${s.eventMore}`}><div><dt>Sequence</dt><dd className={s.mono}>#{e.seq}</dd></div><div><dt>Signature</dt><dd className={s.mono}>{e.signature}</dd></div><div><dt>Actor</dt><dd>{e.actor}</dd></div></dl>}
        </div>)
          : <p className={s.cap} style={{ padding: 18 }}>No events for these filters.</p>}
      </section>
      <aside className={s.quiet} aria-label='Models and retention'>
        <p className={s.title}>Approved models</p>
        <dl className={s.kv}>{models.map(m => <div key={m.name}><dt className={s.mono}>{m.name} {m.version}</dt><dd><Dot tone={m.status === 'deployed' ? 'ok' : 'steel'}>{m.status === 'deployed' ? 'Deployed' : m.status === 'approved' ? 'Approved' : 'Retired'}</Dot></dd></div>)}</dl>
        <p className={s.title} style={{ marginTop: 20 }}>Retention</p>
        <dl className={s.kv}><div><dt>Policy</dt><dd>RP-03 · 7 years</dd></div><div><dt>Legal hold</dt><dd><Dot tone='gold'>Active</Dot></dd></div></dl>
      </aside>
    </div>}
    {section === 'health' && <div className={s.quiet} style={{ maxWidth: 720, marginBottom: 24 }}>
      <p className={s.title}>Approved models</p>
      <dl className={s.kv}>{models.map(m => <div key={m.name}><dt className={s.mono}>{m.name} {m.version}</dt><dd><Dot tone={m.status === 'deployed' ? 'ok' : 'steel'}>{m.status === 'deployed' ? 'Deployed' : m.status === 'approved' ? 'Approved' : 'Retired'}</Dot></dd></div>)}</dl>
    </div>}
    {section !== 'logs' && <div className={s.health}><ShieldCheck size={26} />{[['Chain of custody', 'Intact'], ['Signatures', `${Math.round(audit.filter(e => e.verified).length / Math.max(1, audit.length) * 100)}% verified`], ['Hash checks', 'Consistent'], ['Tamper events', 'None']].map(([k, v]) => <div key={k}><span className={s.cap}>{k}</span><b>{v}</b></div>)}</div>}
  </div>;
}
