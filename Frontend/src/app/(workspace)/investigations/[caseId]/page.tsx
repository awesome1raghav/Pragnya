import type { Metadata } from 'next';
import { CaseOverviewScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Investigation — NEXTRON' };

export default function Page() { return <CaseOverviewScreen />; }
