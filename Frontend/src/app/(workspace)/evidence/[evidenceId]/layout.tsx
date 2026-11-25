import { Suspense } from 'react';
import { WorkbenchRoute } from '@/modules/evidence/EvidencePages';

/* One workbench for /evidence/:id and its tools, so switching tools keeps it mounted. */
export default function EvidenceLayout({ children }: { children: React.ReactNode }) {
  return <Suspense><WorkbenchRoute>{children}</WorkbenchRoute></Suspense>;
}
