import type { Metadata } from 'next';
import { ReportsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Reports — NEXTRON' };

export default function Page() { return <ReportsScreen />; }
