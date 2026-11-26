import type { Metadata } from 'next';
import { CaseGraphScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence graph — NEXTRON' };

export default function Page() { return <CaseGraphScreen />; }
