import type { Metadata } from 'next';
import { ReportListScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Reports — NEXTRON' };

export default function Page() { return <ReportListScreen />; }
