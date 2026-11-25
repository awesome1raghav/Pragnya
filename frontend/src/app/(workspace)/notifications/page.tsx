import type { Metadata } from 'next';
import { NotificationsScreen } from '@/modules/screens';

export const metadata: Metadata = { title: 'Notifications — NEXTRON' };

export default function Page() { return <NotificationsScreen />; }
