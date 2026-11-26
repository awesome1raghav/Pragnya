import type { Metadata } from 'next';
import { EvidenceMetadataScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence metadata — NEXTRON' };

export default function Page() { return <EvidenceMetadataScreen />; }
