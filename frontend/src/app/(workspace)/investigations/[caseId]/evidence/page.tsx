import type { Metadata } from 'next';
import { CaseEvidenceScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Case evidence — NEXTRON' };

export default function Page() { return <CaseEvidenceScreen />; }
