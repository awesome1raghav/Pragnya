import type { Metadata } from 'next';
import { IntegrityScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Integrity — NEXTRON' };

export default function Page() { return <IntegrityScreen />; }
