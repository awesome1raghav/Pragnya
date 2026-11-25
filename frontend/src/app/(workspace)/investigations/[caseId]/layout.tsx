import CaseShell from '@/modules/investigations/CaseShell';

/* Unknown IDs never reach here with the demo data (src/proxy.ts answers 404 first). */
export default async function CaseLayout({ children, params }: { children: React.ReactNode; params: Promise<{ caseId: string }> }) {
  return <CaseShell caseId={decodeURIComponent((await params).caseId)}>{children}</CaseShell>;
}
