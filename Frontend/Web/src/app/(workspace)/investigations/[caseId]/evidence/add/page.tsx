import type { Metadata } from 'next';
import { CaseAddEvidenceScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Add evidence — NEXTRON' };

export default function Page() { return <CaseAddEvidenceScreen />; }
