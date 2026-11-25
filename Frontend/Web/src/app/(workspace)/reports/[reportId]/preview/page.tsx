import type { Metadata } from 'next';
import { ReportScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Report preview — NEXTRON' };

export default function Page() { return <ReportScreen preview />; }
