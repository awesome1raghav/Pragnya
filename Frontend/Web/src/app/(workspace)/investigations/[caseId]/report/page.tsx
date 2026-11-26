import type { Metadata } from 'next';
import { CaseReportScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Report — NEXTRON' };

export default function Page() { return <CaseReportScreen />; }
