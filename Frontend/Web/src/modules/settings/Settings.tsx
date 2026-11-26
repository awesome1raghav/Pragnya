'use client';

/* /settings. Preferences that work today are kept in this browser and labelled so; system configuration
   is shown read-only and contains no secrets. Settings that need a backend say they are not built. */
import { useEffect, useState } from 'react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { API_BASE } from '@/api';
import { useLiveness, useStorageStatus } from '@/api/hooks';
import { PageHead, SecHead, Unavailable } from '@/components/ui';
import { bytes } from '@/utils/labels';
import { useWorkspace } from '@/layouts/MainLayout';

export default function Settings() {
  const { notify } = useWorkspace();
  const live = useLiveness();
  const storage = useStorageStatus();
  const [railPref, setRailPref] = useState<'auto' | 'open' | 'closed'>('auto');
  const [remembered, setRemembered] = useState<string | null>(null);
  useEffect(() => {
    try { const v = localStorage.getItem('nx-rail'); setRailPref(v === '1' ? 'open' : v === '0' ? 'closed' : 'auto'); setRemembered(sessionStorage.getItem('nx-last-case')); } catch { /* storage unavailable */ }
  }, []);
  const saveRail = (v: typeof railPref) => {
    setRailPref(v);
    try { if (v === 'auto') localStorage.removeItem('nx-rail'); else localStorage.setItem('nx-rail', v === 'open' ? '1' : '0'); notify('Saved in this browser; applies on the next page load'); } catch { notify('This browser blocks local storage', 'alert'); }
  };
  const forget = () => { try { sessionStorage.removeItem('nx-last-case'); setRemembered(null); notify('Forgot the last opened investigation'); } catch { /* ignore */ } };

  return <div className={s.page} style={{ maxWidth: 1100 }}>
    <PageHead title='Settings' desc='Your interface preferences, and read-only facts about this installation.' />
    <div className={p.grid2}>
      <div className={p.stack}>
        <section className={s.panel} aria-label='Interface'>
          <SecHead title='Interface'><span className={s.cap}>Stored in this browser only</span></SecHead>
          <label className={s.field}><span>Sidebar</span>
            <select className={s.input} value={railPref} onChange={e => saveRail(e.target.value as typeof railPref)}>
              <option value='auto'>Labelled on wide screens, icons otherwise</option><option value='open'>Always labelled</option><option value='closed'>Icons only</option>
            </select></label>
          <div className={p.formFoot}><span className={s.cap}>Last opened investigation remembered for this tab: <span className={s.mono}>{remembered ?? 'none'}</span></span>{remembered && <button className={`${s.btn} ${s.sm}`} onClick={forget}>Forget it</button>}</div>
          <p className={s.cap}>Times are shown in UTC throughout, matching the recorded evidence history.</p>
        </section>
        <section className={s.panel} aria-label='Installation'>
          <SecHead title='Installation'><span className={s.cap}>Read-only</span></SecHead>
          <dl className={s.kv}>
            <div><dt>API address</dt><dd className={s.mono} style={{ fontSize: 12 }}>{API_BASE}</dd></div>
            <div><dt>API version</dt><dd>{live.data ? `v${live.data.version} (${live.data.environment})` : live.error ? 'unreachable' : '…'}</dd></div>
            <div><dt>Access</dt><dd>Single local operator, no sign-in</dd></div>
            <div><dt>Upload limit</dt><dd>{storage.data ? `${bytes(storage.data.max_upload_bytes)} per file` : storage.error ? 'unknown' : '…'}</dd></div>
          </dl>
          <p className={s.cap}>Change the API address with <span className={s.mono}>NEXT_PUBLIC_NEXTRON_API</span> in <span className={s.mono}>Frontend/Web/.env.local</span>. Server settings live in <span className={s.mono}>Backend/.env</span> and are never sent to the browser.</p>
        </section>
      </div>
      <div className={p.stack}>
        <Unavailable title='Notification, analysis and export preferences' modules={['Preferences API']} step='plan Step 8'>
          <ul>
            <li>Notification preferences need notifications, which come from the event stream (Step 3).</li>
            <li>Analysis defaults (which engines run automatically) need T-MIR (Step 3).</li>
            <li>Export preferences need reports (Step 7).</li>
            <li>Storage and retention configuration are server-side and will stay out of the browser.</li>
          </ul>
        </Unavailable>
      </div>
    </div>
  </div>;
}
