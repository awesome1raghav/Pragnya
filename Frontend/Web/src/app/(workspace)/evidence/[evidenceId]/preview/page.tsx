import type { Metadata } from 'next';
import { EvidencePreviewScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence preview — NEXTRON' };

export default function Page() { return <EvidencePreviewScreen />; }
