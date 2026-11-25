import type { Metadata } from 'next';
import { SystemScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'System — NEXTRON' };

export default function Page() { return <SystemScreen />; }
