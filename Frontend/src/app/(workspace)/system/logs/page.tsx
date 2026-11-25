import type { Metadata } from 'next';
import { SystemScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Audit log — NEXTRON' };

export default function Page() { return <SystemScreen section='logs' />; }
