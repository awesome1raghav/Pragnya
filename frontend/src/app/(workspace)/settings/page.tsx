import type { Metadata } from 'next';
import { SettingsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Settings — NEXTRON' };

export default function Page() { return <SettingsScreen />; }
