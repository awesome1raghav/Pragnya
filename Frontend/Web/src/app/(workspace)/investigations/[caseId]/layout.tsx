import CaseShell from '@/modules/investigations/CaseShell';

/* Every /investigations/:caseId page shares the case frame; it loads the case and handles unknown IDs. */
export default function CaseLayout({ children }: { children: React.ReactNode }) {
  return <CaseShell>{children}</CaseShell>;
}
