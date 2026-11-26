import type { Metadata } from 'next';
import { EvidenceTimelineScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Custody timeline — NEXTRON' };

export default function Page() { return <EvidenceTimelineScreen />; }
