'use client';

/* /settings. Operator preferences are stored by the backend (GET/PATCH /preferences) and applied there: which events
   become notifications, whether uploads are analysed automatically, the default report download. Saving names the
   version the form was loaded from; if another tab saved first, the save is refused and the form shows what is stored
   now. Interface choices stay in this browser. Server configuration is read-only and never includes secrets. */
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import st from './settings.module.css';
import { API_BASE, api, ApiError, type NotificationPrefs, type PreferenceDocument } from '@/api';
import { usePreferences, useSystemConfig } from '@/api/hooks';
import { invalidate } from '@/api/query';
import { Load, PageHead, SecHead } from '@/components/ui';
import { bytes } from '@/utils/labels';
import { applyDensity, useWorkspace } from '@/layouts/MainLayout';

const NOTIFY: [keyof NotificationPrefs, string][] = [
  ['runs_completed', 'An analysis run completed'], ['runs_partial', 'A run completed partially'], ['runs_failed', 'A run failed'],
  ['runs_cancelled', 'A run was cancelled'], ['sources', 'A source could not be retrieved'], ['reports', 'A report was generated or failed'],
];

const GROUPS = [
  { id: 'work', title: 'How NEXTRON works for you', note: 'Stored on the server and applied there, so every tab and window follows them.' },
  { id: 'browser', title: 'This browser', note: 'Kept in this browser only.' },
  { id: 'install', title: 'This installation', note: 'Read-only facts. Server settings live in Backend/.env and never reach the browser.' },
] as const;

export default function Settings() {
  return <div className={s.page} style={{ maxWidth: 1040 }}>
    <PageHead title='Settings' desc='Your preferences, applied by the backend, and read-only facts about this installation.' />
    <div className={st.layout}>
      <nav className={st.index} aria-label='Settings sections'>{GROUPS.map(g => <a key={g.id} href={`#${g.id}`}>{g.title}</a>)}</nav>
      <div className={st.groups}>
        {GROUPS.map((g, i) => <motion.section key={g.id} id={g.id} className={st.group} aria-labelledby={`${g.id}-title`}
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, duration: .22, ease: [.22, 1, .36, 1] }}>
          <header><h2 id={`${g.id}-title`}>{g.title}</h2><p>{g.note}</p></header>
          {g.id === 'work' ? <PreferencesForm /> : g.id === 'browser' ? <Interface /> : <Installation />}
        </motion.section>)}
      </div>
    </div>
  </div>;
}

function PreferencesForm() {
  const { notify } = useWorkspace();
  const q = usePreferences();
  const cfg = useSystemConfig();
  const [draft, setDraft] = useState<PreferenceDocument | null>(null);
  const [base, setBase] = useState<{ version: number; doc: PreferenceDocument } | null>(null);  // what the form was loaded from
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const stored = q.data;
  const dirty = !!(draft && base && JSON.stringify(draft) !== JSON.stringify(base.doc));
  const adopt = (st: { version: number; preferences: PreferenceDocument }) => { setDraft(st.preferences); setBase({ version: st.version, doc: st.preferences }); };
  // follow the stored document (initial load, or another tab saved) unless there are unsaved edits here
  useEffect(() => { if (stored && (!base || (!dirty && stored.version !== base.version))) adopt(stored); }, [stored]);  // eslint-disable-line react-hooks/exhaustive-deps
  const changedElsewhere = !!(stored && base && dirty && stored.version !== base.version);

  const save = async () => {
    if (!draft || !base) return;
    setBusy(true); setConflict(false);
    try { const r = await api.preferences.update(base.version, draft); adopt(r); notify(`Preferences saved (version ${r.version})`); invalidate('preferences'); }
    catch (e) {
      if (e instanceof ApiError && e.code === 'PREFERENCES_CONFLICT') { setConflict(true); setBase(null); invalidate('preferences'); }  // the refetch re-adopts what is stored
      else notify(e instanceof ApiError ? e.message : 'Preferences could not be saved', 'alert');
    } finally { setBusy(false); }
  };
  const set = (fn: (d: PreferenceDocument) => PreferenceDocument) => setDraft(d => d && fn(structuredClone(d)));

  return <section className={s.panel} aria-label='Preferences'>
    <SecHead title='Preferences'><span className={s.cap}>{stored ? `Stored on the server · version ${stored.version}` : ''}</span></SecHead>
    <Load q={q} rows={4}>{st => draft && <>
      {conflict && <p className={p.warnLine} role='alert'>Another tab or window saved preferences first. The form now shows what is stored; apply your change again.</p>}
      {changedElsewhere && !conflict && <p className={p.warnLine} role='note'>Preferences were changed in another tab (now version {st.version}). Saving here will be refused; reload them first.
        {' '}<button className={`${s.btn} ${s.sm}`} onClick={() => adopt(st)}>Reload</button></p>}
      <fieldset style={{ border: 0, padding: 0, margin: '0 0 14px' }}><legend className={s.muted} style={{ fontSize: 12, marginBottom: 6 }}>Notify me when</legend>
        {NOTIFY.map(([k, label]) => <label key={k} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', fontSize: 13 }}>
          <input type='checkbox' checked={draft.notifications[k]} onChange={e => set(d => { d.notifications[k] = e.target.checked; return d; })} aria-label={label} />{label}</label>)}
        <p className={s.cap}>Evidence integrity failures are always notified.</p>
      </fieldset>
      <label className={s.field}><span>Analyse new evidence automatically</span>
        <select className={s.input} aria-label='Automatic analysis' value={draft.analysis.auto_analyze_on_upload === null ? 'server' : draft.analysis.auto_analyze_on_upload ? 'on' : 'off'}
          onChange={e => set(d => { d.analysis.auto_analyze_on_upload = e.target.value === 'server' ? null : e.target.value === 'on'; return d; })}>
          <option value='server'>Server default{cfg.data ? ` (${cfg.data.uploads.auto_analyze_default ? 'on' : 'off'})` : ''}</option>
          <option value='on'>On: queue a run for every upload and retrieved source</option><option value='off'>Off: start runs myself</option>
        </select></label>
      <label className={s.field}><span>Default report download</span>
        <select className={s.input} aria-label='Default report download' value={draft.reports.default_download} onChange={e => set(d => { d.reports.default_download = e.target.value as 'pdf' | 'json'; return d; })}>
          <option value='pdf'>PDF</option><option value='json'>JSON</option></select></label>
      <div className={p.formFoot}>
        <span className={s.cap}>{dirty ? 'Unsaved changes' : 'Saved'}{st.updated_at ? ` · last saved ${st.updated_at.slice(0, 19).replace('T', ' ')} UTC` : ' · defaults (never saved)'}</span>
        <button className={`${s.btn} ${s.primary}`} disabled={!dirty || busy} onClick={save}>{busy ? 'Saving…' : 'Save preferences'}</button>
      </div>
    </>}</Load>
  </section>;
}

function Interface() {
  const { notify } = useWorkspace();
  const [railPref, setRailPref] = useState<'auto' | 'open' | 'closed'>('auto');
  const [remembered, setRemembered] = useState<string | null>(null);
  const [density, setDensity] = useState<'comfortable' | 'compact'>('comfortable');
  useEffect(() => {
    const read = () => { try { const v = localStorage.getItem('nx-rail'); setRailPref(v === '1' ? 'open' : v === '0' ? 'closed' : 'auto'); setRemembered(sessionStorage.getItem('nx-last-case')); setDensity(localStorage.getItem('nx-density') === 'compact' ? 'compact' : 'comfortable'); } catch { /* storage unavailable */ } };
    read();
    window.addEventListener('storage', read);  // another tab changed it
    return () => window.removeEventListener('storage', read);
  }, []);
  const saveRail = (v: typeof railPref) => {
    setRailPref(v);
    try { if (v === 'auto') localStorage.removeItem('nx-rail'); else localStorage.setItem('nx-rail', v === 'open' ? '1' : '0'); notify('Saved in this browser; applies on the next page load'); } catch { notify('This browser blocks local storage', 'alert'); }
  };
  const saveDensity = (v: typeof density) => { setDensity(v); try { localStorage.setItem('nx-density', v); applyDensity(); notify(v === 'compact' ? 'Compact spacing on' : 'Comfortable spacing on'); } catch { notify('This browser blocks local storage', 'alert'); } };
  const forget = () => { try { sessionStorage.removeItem('nx-last-case'); setRemembered(null); notify('Forgot the last opened investigation'); } catch { /* ignore */ } };
  return <section className={s.panel} aria-label='Interface'>
    <SecHead title='Interface'><span className={s.cap}>Stored in this browser only</span></SecHead>
    <label className={s.field}><span>Sidebar</span>
      <select className={s.input} value={railPref} onChange={e => saveRail(e.target.value as typeof railPref)}>
        <option value='auto'>Labelled on wide screens, icons otherwise</option><option value='open'>Always labelled</option><option value='closed'>Icons only</option>
      </select></label>
    <label className={s.field}><span>Density</span>
      <select className={s.input} value={density} onChange={e => saveDensity(e.target.value as typeof density)} aria-label='Density'>
        <option value='comfortable'>Comfortable: more space, easier reading</option><option value='compact'>Compact: more on screen, same text size</option>
      </select></label>
    <div className={p.formFoot}><span className={s.cap}>Last opened investigation remembered for this tab: <span className={s.mono}>{remembered ?? 'none'}</span></span>{remembered && <button className={`${s.btn} ${s.sm}`} onClick={forget}>Forget it</button>}</div>
    <p className={s.cap}>Times are shown in UTC throughout, matching the recorded evidence history.</p>
  </section>;
}

function Installation() {
  const q = useSystemConfig();
  return <section className={s.panel} aria-label='Installation'>
    <SecHead title='Installation'><span className={s.cap}>Read-only</span></SecHead>
    <Load q={q} rows={6}>{c => <dl className={s.kv}>
      <div><dt>API address</dt><dd className={s.mono} style={{ fontSize: 12 }}>{API_BASE}</dd></div>
      <div><dt>API version</dt><dd>v{c.version} ({c.environment})</dd></div>
      <div><dt>Access</dt><dd>Single local operator ({c.operator}), no sign-in</dd></div>
      <div><dt>Upload limit</dt><dd>{bytes(c.uploads.max_bytes)} per file</dd></div>
      <div><dt>Jobs</dt><dd>{c.jobs.max_attempts} attempts · lease {c.jobs.lease_seconds} s · job timeout {Math.round(c.jobs.job_timeout_seconds / 60)} min · module timeout {Math.round(c.jobs.module_timeout_seconds / 60)} min</dd></div>
      <div><dt>Detectors</dt><dd>{c.detectors.enabled ? `On · image ${c.detectors.image ?? 'none'} · speech ${c.detectors.speech ?? 'none'}` : 'Off'}</dd></div>
      <div><dt>Projections</dt><dd>Neo4j {c.projections.neo4j ? 'on' : 'off'} · Qdrant {c.projections.qdrant ? 'on' : 'off'}</dd></div>
      <div><dt>Web visual search</dt><dd>{c.web_visual_search?.enabled ? (c.web_visual_search.key_configured ? 'On (opt-in per search)' : 'Enabled, but no provider key') : 'Off'}</dd></div>
    </dl>}</Load>
    <p className={s.cap}>Change the API address with <span className={s.mono}>NEXT_PUBLIC_NEXTRON_API</span> in <span className={s.mono}>Frontend/Web/.env.local</span>. Server settings live in <span className={s.mono}>Backend/.env</span> and are never sent to the browser.</p>
  </section>;
}
