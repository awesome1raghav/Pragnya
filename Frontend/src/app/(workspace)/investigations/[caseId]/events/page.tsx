import type { Metadata } from 'next';
import { CaseEventsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Events — NEXTRON' };

export default function Page() { return <CaseEventsScreen />; }
