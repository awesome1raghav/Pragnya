'use client';

/* /investigations/new. Validates in the browser with the same limits as the API, shows the API's own
   validation messages per field if it still refuses, and navigates only after the case is committed. */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { LoaderCircle, Plus } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import cs from './case.module.css';
import { ApiError, CASE_CATEGORIES, CASE_PRIORITIES, api, type CaseCategory, type CasePriority } from '@/api';
import { invalidate, prime } from '@/api/query';
import { ErrorState, PageHead } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { categoryLabel, priorityLabel } from '@/utils/labels';

type Form = { title: string; category: CaseCategory; priority: CasePriority; description: string; objectives: string; tags: string; notes: string };
const LIMITS = { title: 200, description: 10_000, objectives: 5_000, notes: 20_000 };

export function fieldErrors(e: ApiError | null): Record<string, string> {
  if (!e || e.code !== 'VALIDATION_ERROR' || !Array.isArray(e.details)) return {};
  const out: Record<string, string> = {};
  for (const d of e.details as { location?: (string | number)[]; message?: string }[]) {
    const field = d.location?.[1]; if (typeof field === 'string' && !out[field]) out[field] = d.message ?? 'Invalid value';
  }
  return out;
}

export const parseTags = (raw: string) => [...new Set(raw.split(',').map(t => t.trim()).filter(Boolean))];

export default function NewInvestigation() {
  const router = useRouter();
  const { notify } = useWorkspace();
  const [f, setF] = useState<Form>({ title: '', category: 'OTHER', priority: 'MEDIUM', description: '', objectives: '', tags: '', notes: '' });
  const [addEvidence, setAddEvidence] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [touched, setTouched] = useState(false);
  const set = <K extends keyof Form>(k: K) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF(v => ({ ...v, [k]: e.target.value }));

  const tags = parseTags(f.tags);
  const local: Record<string, string> = {};
  if (!f.title.trim()) local.title = 'A title is required';
  else if (f.title.trim().length > LIMITS.title) local.title = `At most ${LIMITS.title} characters`;
  if (tags.length > 20) local.tags = 'At most 20 tags';
  if (tags.some(t => t.length > 50)) local.tags = 'Each tag is at most 50 characters';
  const server = fieldErrors(error);
  const errs = { ...server, ...(touched ? local : {}) };

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setTouched(true);
    if (Object.keys(local).length) return;
    setBusy(true); setError(null);
    try {
      const c = await api.cases.create({ title: f.title.trim(), category: f.category, priority: f.priority, description: f.description.trim() || null, objectives: f.objectives.trim() || null, tags, notes: f.notes.trim() || null });
      prime(`case:${c.case_id}`, c);
      invalidate('cases');
      notify(`Created ${c.case_number}`);
      router.push(addEvidence ? paths.caseAddEvidence(c.case_id) : paths.case(c.case_id));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'CLIENT_ERROR', String(err)));
      setBusy(false);
    }
  }

  const Err = ({ k }: { k: string }) => errs[k] ? <span className={p.fieldError} role='alert'>{errs[k]}</span> : null;
  return <div className={s.page} style={{ maxWidth: 1120 }}>
    <PageHead title='New investigation' desc='Name what you are examining and what it must establish. Only the title is required; everything else can be added later.' />
    <div className={cs.newWrap}>
      <form className={`${p.form} ${cs.steps}`} onSubmit={submit} noValidate>
        <section className={cs.step} aria-label='What this investigation is'>
          <div className={cs.stepHead}><span>1</span><div><b>What is this investigation?</b> <small>The title others will recognise it by, and its purpose.</small></div></div>
          <label className={s.field}><span>Title<span className={p.req} aria-hidden='true'>*</span></span>
            <input className={s.input} value={f.title} onChange={set('title')} maxLength={LIMITS.title + 20} required aria-invalid={!!errs.title} placeholder='e.g. Viral clip of the harbour fire' autoFocus />
            <Err k='title' /></label>
          <label className={s.field}><span>Objectives</span>
            <textarea className={`${s.input} ${p.textarea}`} value={f.objectives} onChange={set('objectives')} maxLength={LIMITS.objectives} placeholder='What must this investigation establish? e.g. whether the audio was replaced; where the clip first appeared' />
            <span className={p.fieldHint}>{f.objectives.length} / {LIMITS.objectives}</span><Err k='objectives' /></label>
        </section>
        <section className={cs.step} aria-label='Context'>
          <div className={cs.stepHead}><span>2</span><div><b>Context</b> <small>How it reached you and how urgent it is.</small></div></div>
          <div className={p.formGrid}>
            <label className={s.field}><span>Category</span><select className={s.input} value={f.category} onChange={set('category')}>{CASE_CATEGORIES.map(c => <option key={c} value={c}>{categoryLabel[c]}</option>)}</select><Err k='category' /></label>
            <label className={s.field}><span>Priority</span><select className={s.input} value={f.priority} onChange={set('priority')}>{CASE_PRIORITIES.map(x => <option key={x} value={x}>{priorityLabel[x]}</option>)}</select><Err k='priority' /></label>
            <label className={`${s.field} ${p.formWide}`}><span>Description</span>
              <textarea className={`${s.input} ${p.textarea}`} value={f.description} onChange={set('description')} maxLength={LIMITS.description} placeholder='How the media reached you and why it needs examining' /><Err k='description' /></label>
            <label className={s.field}><span>Tags <span className={s.muted}>(comma-separated)</span></span><input className={s.input} value={f.tags} onChange={set('tags')} placeholder='video, harbour, viral' aria-invalid={!!errs.tags} /><Err k='tags' /></label>
            <label className={s.field}><span>Investigator notes</span><input className={s.input} value={f.notes} onChange={set('notes')} maxLength={LIMITS.notes} placeholder='Optional' /><Err k='notes' /></label>
          </div>
        </section>
        {error && !Object.keys(server).length && <ErrorState error={error} title='The investigation was not created' />}
        <div className={p.formFoot}>
          <button className={`${s.btn} ${s.primary}`} type='submit' disabled={busy}>{busy ? <><LoaderCircle size={15} className={s.spin} />Creating…</> : <><Plus size={15} />Create investigation</>}</button>
          <Link className={`${s.btn} ${s.ghost}`} href={paths.investigations()}>Cancel</Link>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: 'var(--soft)' }}><input type='checkbox' checked={addEvidence} onChange={e => setAddEvidence(e.target.checked)} />Add evidence next</label>
        </div>
      </form>
      <aside className={cs.aside} aria-label='What happens next'>
        <b>What happens next</b>
        <ol>
          <li>The investigation is created and logged as its first event, by the local operator.</li>
          <li>You add the original files. Each is hashed on the server and stored read-only.</li>
          <li>Analysis runs on each file; findings appear as modules finish.</li>
          <li>You review the findings, record a conclusion and generate the report.</li>
        </ol>
      </aside>
    </div>
  </div>;
}
