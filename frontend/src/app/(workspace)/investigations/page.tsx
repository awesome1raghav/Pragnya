import type { Metadata } from 'next';
import { InvestigationsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Investigations — NEXTRON' };

export default function Page() { return <InvestigationsScreen />; }
