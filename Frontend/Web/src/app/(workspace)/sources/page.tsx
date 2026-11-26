import type { Metadata } from 'next';
import { SourcesScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Sources — NEXTRON' };

export default function Page() { return <SourcesScreen />; }
