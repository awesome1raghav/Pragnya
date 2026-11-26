import EvidenceShell from '@/modules/evidence/EvidenceShell';

/* Every /evidence/:evidenceId page shares the evidence frame; switching tools keeps it mounted. */
export default function EvidenceLayout({ children }: { children: React.ReactNode }) {
  return <EvidenceShell>{children}</EvidenceShell>;
}
