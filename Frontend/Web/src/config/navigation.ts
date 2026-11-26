/* Global navigation (Flowchart B): the eleven application destinations, in order.
   Number keys 1–9 jump to the first nine; the palette (Ctrl K) reaches all of them.
   Pages that carry an investigation context keep it when you move between them (`scoped`). */
import { Bell, FileText, Film, FolderSearch, GitBranch, Globe2, LayoutGrid, Network, Scale, Settings, Share2 } from 'lucide-react';
import { paths } from './routes';

export const NAV = [
  { href: paths.dashboard(), label: 'Dashboard', icon: LayoutGrid, match: '/dashboard', scoped: false },
  { href: paths.investigations(), label: 'Investigations', icon: FolderSearch, match: '/investigations', scoped: false },
  { href: '/evidence', label: 'Evidence', icon: Film, match: '/evidence', scoped: true },
  { href: '/sources', label: 'Sources', icon: Globe2, match: '/sources', scoped: true },
  { href: '/lineage', label: 'Lineage', icon: GitBranch, match: '/lineage', scoped: true },
  { href: '/intelligence', label: 'Intelligence', icon: Network, match: '/intelligence', scoped: true },
  { href: '/graph', label: 'Evidence graph', icon: Share2, match: '/graph', scoped: true },
  { href: '/reports', label: 'Reports', icon: FileText, match: '/reports', scoped: true },
  { href: paths.notifications(), label: 'Notifications', icon: Bell, match: '/notifications', scoped: false },
  { href: paths.system(), label: 'System', icon: Scale, match: '/system', scoped: false },
  { href: paths.settings(), label: 'Settings', icon: Settings, match: '/settings', scoped: false },
] as const;

export const isActive = (pathname: string, match: string) => pathname === match || pathname.startsWith(`${match}/`);
