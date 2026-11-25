import type { Metadata } from 'next';
import { EvidenceListScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence — NEXTRON' };

export default function Page() { return <EvidenceListScreen />; }
