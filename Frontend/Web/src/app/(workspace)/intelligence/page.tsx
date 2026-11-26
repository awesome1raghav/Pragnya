import type { Metadata } from 'next';
import { IntelligenceScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Intelligence — NEXTRON' };

export default function Page() { return <IntelligenceScreen />; }
