import type { Metadata } from 'next';
import { SystemHealthScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Health checks — NEXTRON' };

export default function Page() { return <SystemHealthScreen />; }
