import type { Metadata } from 'next';
import { DashboardScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Dashboard — NEXTRON' };

export default function Page() { return <DashboardScreen />; }
