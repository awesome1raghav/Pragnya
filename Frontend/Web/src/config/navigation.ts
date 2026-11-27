/* Global navigation (Flowchart B): the eleven application destinations, in order, in three groups: the investigation
   and its evidence, the analytical workspaces built on it, and operating the installation. Number keys 1–9 jump to the
   first nine; the palette (Ctrl K) reaches all of them. Pages that carry an investigation context keep it (`scoped`). */
import { Bell, FileText, Film, FolderSearch, GitBranch, Globe2, LayoutGrid, Network, Scale, Settings, Share2 } from 'lucide-react';
import { paths } from './routes';

export const NAV_GROUPS = [
  { id: 'investigate', label: 'Investigate' },
  { id: 'analyse', label: 'Analyse and report' },
  { id: 'operate', label: 'Operate' },
] as const;

export const NAV = [
  { href: paths.dashboard(), label: 'Dashboard', group: 'investigate', icon: LayoutGrid, match: '/dashboard', scoped: false },
  { href: paths.investigations(), label: 'Investigations', group: 'investigate', icon: FolderSearch, match: '/investigations', scoped: false },
  { href: '/evidence', label: 'Evidence', group: 'investigate', icon: Film, match: '/evidence', scoped: true },
  { href: '/sources', label: 'Sources', group: 'investigate', icon: Globe2, match: '/sources', scoped: true },
  { href: '/lineage', label: 'Lineage', group: 'analyse', icon: GitBranch, match: '/lineage', scoped: true },
  { href: '/intelligence', label: 'Intelligence', group: 'analyse', icon: Network, match: '/intelligence', scoped: true },
  { href: '/graph', label: 'Evidence graph', group: 'analyse', icon: Share2, match: '/graph', scoped: true },
  { href: '/reports', label: 'Reports', group: 'analyse', icon: FileText, match: '/reports', scoped: true },
  { href: paths.notifications(), label: 'Notifications', group: 'operate', icon: Bell, match: '/notifications', scoped: false },
  { href: paths.system(), label: 'System', group: 'operate', icon: Scale, match: '/system', scoped: false },
  { href: paths.settings(), label: 'Settings', group: 'operate', icon: Settings, match: '/settings', scoped: false },
] as const;

export const isActive = (pathname: string, match: string) => pathname === match || pathname.startsWith(`${match}/`);
