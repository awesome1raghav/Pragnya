'use client';

/* Metadata and provenance, layered: a short summary, the observations the modules made, then every extracted field by
   category with search; the raw extractor output only on request. Missing metadata is said to be missing (that is
   common and not suspicious in itself); a valid C2PA signature says who signed, not that the content is true. */
import { useMemo, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import type { Metadata } from '@/api';
import type { ViewerFinding } from './normalize';
import v from './viewer.module.css';

const flatten = (o: unknown, prefix = '', out: [string, string][] = []): [string, string][] => {
  if (o === null || typeof o !== 'object') { out.push([prefix || '(value)', o === null ? '—' : String(o)]); return out; }
  const entries = Array.isArray(o) ? o.map((x, i) => [String(i), x] as const) : Object.entries(o as Record<string, unknown>);
  if (!entries.length) out.push([prefix || '(empty)', Array.isArray(o) ? '[]' : '{}']);
  for (const [k, x] of entries) flatten(x, prefix ? `${prefix}.${k}` : k, out);
  return out;
};

const C2PA: Record<string, { label: string; meaning: string }> = {
  ABSENT: { label: 'No content credentials', meaning: 'The file carries no C2PA manifest. Most media does not; this is not suspicious in itself.' },
  VALID: { label: 'Valid credentials (signer not on a trust list)', meaning: 'The manifest verifies against its signature. That says who signed and what they declared, not that the content is true.' },
  INVALID: { label: 'Invalid credentials', meaning: 'A manifest is present but does not verify: the file or the manifest changed after signing, or the signature is broken.' },
  UNSUPPORTED: { label: 'Format not supported for credentials', meaning: 'The C2PA SDK cannot read credentials from this format.' },
};

export function MetaCanvas({ md, findings }: { md: Metadata | undefined; findings: ViewerFinding[] }) {
  const [q, setQ] = useState('');
  const [raw, setRaw] = useState(false);
  const prv = findings.find(f => f.moduleId === 'NEX-PRV');
  const c2pa = prv ? String(prv.measurement.state ?? '') : '';
  const summary = (md?.summary ?? {}) as Record<string, unknown>;
  const groups = useMemo(() => {
    const rows = flatten(summary).filter(([k]) => !k.endsWith('_note'));
    const by = new Map<string, [string, string][]>();
    for (const [k, x] of rows) { const g = k.split('.')[0]; if (!by.has(g)) by.set(g, []); by.get(g)!.push([k, x]); }
    return [...by.entries()];
  }, [summary]);
  const needle = q.trim().toLowerCase();
  const visible = groups.map(([g, rows]) => [g, needle ? rows.filter(([k, x]) => k.toLowerCase().includes(needle) || x.toLowerCase().includes(needle)) : rows] as const).filter(([, rows]) => rows.length);
  const facts: [string, unknown][] = [['Format', summary.format ?? summary.format_name], ['Dimensions', summary.width && summary.height ? `${String(summary.width)} × ${String(summary.height)}` : null],
    ['Duration', typeof summary.duration_seconds === 'number' ? `${summary.duration_seconds.toFixed(2)} s` : null], ['Encoder', summary.encoder],
    ['EXIF', summary.exif_present === undefined ? null : summary.exif_present ? 'present' : 'none in the file'],
    ['Embedded times', summary.embedded_timestamps && Object.keys(summary.embedded_timestamps as object).length ? Object.entries(summary.embedded_timestamps as Record<string, string>).map(([k, x]) => `${k} ${x}`).join(' · ') : 'none in the file']];

  if (!md) return <div className={v.canvasWrap}><p className={v.empty}>Metadata has not been extracted for this item yet.</p></div>;
  return <div className={`${v.canvasWrap} ${v.metaWrap}`}>
    <section className={v.metaSummary} aria-label='Summary'>
      <dl>{facts.filter(([, x]) => x !== null && x !== undefined && x !== '').map(([k, x]) => <div key={k}><dt>{k}</dt><dd>{String(x)}</dd></div>)}</dl>
      <p className={v.hint}>Extracted by {md.extractor} {md.extractor_version} · {md.status.toLowerCase()} · version {md.version_count}. Embedded values are the file’s own claims and can be absent, wrong or edited.</p>
    </section>
    {prv && <section className={v.prov} data-state={c2pa} aria-label='Provenance'>
      <b>{C2PA[c2pa]?.label ?? prv.title}</b><p>{C2PA[c2pa]?.meaning ?? prv.description}</p>
    </section>}
    <section aria-label='All extracted fields'>
      <label className={v.metaSearch}><Search size={14} /><input value={q} onChange={e => setQ(e.target.value)} placeholder='Search fields and values' aria-label='Search metadata' /></label>
      {visible.length ? visible.map(([g, rows]) => <details key={g} className={v.metaGroup} open={!!needle || rows.length <= 6}>
        <summary><ChevronDown size={14} />{g.replace(/_/g, ' ')}<small>{rows.length}</small></summary>
        <dl>{rows.map(([k, x]) => <div key={k}><dt className={v.mono}>{k.split('.').slice(1).join('.') || k}</dt><dd>{x}</dd></div>)}</dl>
      </details>) : <p className={v.empty}>No field matches “{q}”.</p>}
      <button className={v.textBtn} onClick={() => setRaw(x => !x)} aria-expanded={raw}>{raw ? 'Hide' : 'Show'} the raw extractor output</button>
      {raw && <pre className={v.raw}>{JSON.stringify(md.raw, null, 2)}</pre>}
    </section>
  </div>;
}
