import type { Metadata } from 'next';
import { EvidenceOverviewScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence — NEXTRON' };

export default function Page() { return <EvidenceOverviewScreen />; }
