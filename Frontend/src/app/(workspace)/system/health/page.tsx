import type { Metadata } from 'next';
import { SystemScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'System health — NEXTRON' };

export default function Page() { return <SystemScreen section='health' />; }
