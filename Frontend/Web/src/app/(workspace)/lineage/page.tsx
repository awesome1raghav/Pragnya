import type { Metadata } from 'next';
import { LineageScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Lineage — NEXTRON' };

export default function Page() { return <LineageScreen />; }
