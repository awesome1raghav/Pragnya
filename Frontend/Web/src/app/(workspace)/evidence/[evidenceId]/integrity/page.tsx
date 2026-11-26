import type { Metadata } from 'next';
import { EvidenceIntegrityScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence integrity — NEXTRON' };

export default function Page() { return <EvidenceIntegrityScreen />; }
