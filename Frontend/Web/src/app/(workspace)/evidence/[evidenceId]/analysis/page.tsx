import type { Metadata } from 'next';
import { EvidenceAnalysisScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence analysis — NEXTRON' };

export default function Page() { return <EvidenceAnalysisScreen />; }
