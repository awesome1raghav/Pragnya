import type { Metadata } from 'next';
import { CaseAnalysisScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Analysis — NEXTRON' };

export default function Page() { return <CaseAnalysisScreen />; }
