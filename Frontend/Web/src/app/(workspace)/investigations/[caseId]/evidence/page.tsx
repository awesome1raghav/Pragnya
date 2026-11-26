import type { Metadata } from 'next';
import { CaseEvidenceScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Investigation evidence — NEXTRON' };

export default function Page() { return <CaseEvidenceScreen />; }
