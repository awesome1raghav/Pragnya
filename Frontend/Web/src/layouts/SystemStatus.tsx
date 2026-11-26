'use client';

/* Global system status (Flowchart B): one quiet chip while everything is ready, an explicit warning
   when it is not. Polls the real readiness probe; never assumes a state it has not measured. */
import Link from 'next/link';
import p from '@/styles/platform.module.css';
import { useReadiness } from '@/api/hooks';
import type { ReadinessCheck } from '@/api';
import { paths } from '@/config/routes';

export function useSystemState() {
  const q = useReadiness();
  if (q.data && !q.error) return { tone: 'ok' as const, label: 'System ready', detail: 'Database and evidence storage are ready', q };
  if (q.error?.unreachable) return { tone: 'alert' as const, label: 'API unreachable', detail: q.error.message, q };
  if (q.error) {
    const checks = (q.error.details as { checks?: Record<string, ReadinessCheck> } | null)?.checks;
    const failing = checks ? Object.entries(checks).filter(([, c]) => c.status === 'FAIL').map(([name, c]) => c.reason ?? `${name} failed`) : [];
    return { tone: 'alert' as const, label: 'Not ready', detail: failing.join('; ') || q.error.message, q };
  }
  return { tone: 'mute' as const, label: 'Checking…', detail: 'Waiting for the first readiness check', q };
}

export default function SystemStatus() {
  const st = useSystemState();
  return <Link href={paths.system()} className={`${p.statusChip} ${st.tone === 'ok' ? p.statusQuiet : ''}`} data-tone={st.tone} title={st.detail} aria-label={`System status: ${st.label}. ${st.detail}`}>
    <i aria-hidden='true' /><span>{st.label}</span>
  </Link>;
}

/** Full-width warning under the top bar while the API cannot be reached. */
export function OfflineBanner() {
  const st = useSystemState();
  if (st.tone !== 'alert') return null;
  return <div className={p.banner} role='status'>
    <b>{st.label}.</b><span>{st.detail}</span><Link href={paths.system()}>System status</Link>
  </div>;
}
