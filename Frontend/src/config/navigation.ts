/* The sidebar: only sections that are built. Number keys 1–8 jump to them in this order. */
import { Bell, FileText, Film, FolderSearch, LayoutGrid, Scale, Settings, Share2 } from 'lucide-react';
import { paths } from './routes';

export const NAV = [
  { href: paths.dashboard(), label: 'Dashboard', icon: LayoutGrid, match: '/dashboard' },
  { href: paths.investigations(), label: 'Investigations', icon: FolderSearch, match: '/investigations' },
  { href: paths.evidenceList(), label: 'Evidence', icon: Film, match: '/evidence' },
  { href: paths.graph(), label: 'Evidence graph', icon: Share2, match: '/graph' },
  { href: paths.reports(), label: 'Reports', icon: FileText, match: '/reports' },
  { href: paths.notifications(), label: 'Notifications', icon: Bell, match: '/notifications' },
  { href: paths.system(), label: 'System', icon: Scale, match: '/system' },
  { href: paths.settings(), label: 'Settings', icon: Settings, match: '/settings' },
] as const;

export const isActive = (pathname: string, match: string) => pathname === match || pathname.startsWith(`${match}/`);
