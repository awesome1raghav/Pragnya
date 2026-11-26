import type { Metadata } from 'next';
import { CasePendingScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Evidence graph — NEXTRON' };

export default function Page() { return <CasePendingScreen kind='graph' />; }
