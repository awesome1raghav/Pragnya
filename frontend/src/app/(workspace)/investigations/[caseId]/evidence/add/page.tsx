import type { Metadata } from 'next';
import { NewInvestigationScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Add evidence — NEXTRON' };

export default function Page() { return <NewInvestigationScreen />; }
