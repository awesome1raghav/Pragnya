import type { Metadata } from 'next';
import { CasePendingScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Report — NEXTRON' };

export default function Page() { return <CasePendingScreen kind='report' />; }
