import MainLayout from '@/layouts/MainLayout';

/* Every workspace address shares one shell: navigation, data, the command palette and notifications. */
export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <MainLayout>{children}</MainLayout>;
}
