import type { Metadata } from 'next';
import { SystemLogsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Logs — NEXTRON' };

export default function Page() { return <SystemLogsScreen />; }
