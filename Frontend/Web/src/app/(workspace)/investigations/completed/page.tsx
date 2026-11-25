import type { Metadata } from 'next';
import { InvestigationsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Completed investigations — NEXTRON' };

export default function Page() { return <InvestigationsScreen filter='completed' />; }
