import type { Metadata } from 'next';
import { CaseTimelineScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Timeline — NEXTRON' };

export default function Page() { return <CaseTimelineScreen />; }
