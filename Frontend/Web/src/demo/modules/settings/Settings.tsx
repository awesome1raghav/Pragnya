'use client';

/* /settings: the preferences this frontend actually has. Account, privacy and permission settings arrive
   with authentication, so they are not shown here. */
import s from '@/styles/workspace.module.css';
import { usingMock } from '@/demo/api';
import { PageHead, type Ctx } from '@/demo/components/ui';
import { NAV } from '@/demo/config/navigation';
import { useWorkspace } from '@/demo/layouts/MainLayout';

const SHORTCUTS: [string, string][] = [['Ctrl K', 'Search or run a command'], ['Ctrl B', 'Labelled or icon-only sidebar'], [`1–${NAV.length}`, 'Jump to a sidebar section'], ['V · E · T · M', 'Workbench tools: viewer, examine, timeline, metadata'], ['[ · ]', 'Hide the evidence or findings panel'], ['Space', 'Play or pause a clip'], ['C', 'Compare original and error level']];

export default function Settings(_: Ctx) {
  const { rail: labelled, toggleRail } = useWorkspace();
  return <div className={s.page}>
    <PageHead title='Settings' desc='Preferences for this browser.' />
    <div className={s.settings}>
      <section className={s.setRow}>
        <div><b>Labelled sidebar</b><p>Show section names beside the icons. Ctrl B switches it anywhere.</p></div>
        <label className={s.check}><input type='checkbox' checked={labelled} onChange={toggleRail} />{labelled ? 'On' : 'Off'}</label>
      </section>
      <section className={s.setRow}>
        <div><b>Data source</b><p>{usingMock ? 'Demo data, held in this browser. Set NEXT_PUBLIC_NEXTRON_API to connect the NEXTRON backend.' : `Connected to ${process.env.NEXT_PUBLIC_NEXTRON_API}.`}</p></div>
        <span className={s.cap}>{usingMock ? 'Demo' : 'Live'}</span>
      </section>
      <section className={s.setRow}>
        <div><b>Motion</b><p>The workspace follows your system’s reduce-motion setting: transitions are removed, nothing else changes.</p></div>
        <span className={s.cap}>System</span>
      </section>
      <section className={s.setBlock}>
        <b>Keyboard</b>
        <dl className={s.kv}>{SHORTCUTS.map(([k, v]) => <div key={k}><dt><kbd className={s.kbd}>{k}</kbd></dt><dd>{v}</dd></div>)}</dl>
      </section>
    </div>
  </div>;
}
