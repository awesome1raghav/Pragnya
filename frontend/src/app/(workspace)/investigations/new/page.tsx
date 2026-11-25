import type { Metadata } from 'next';
import { NewInvestigationScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'New investigation — NEXTRON' };

export default function Page() { return <NewInvestigationScreen />; }
