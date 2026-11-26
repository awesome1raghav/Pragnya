'use client';

/* The active investigation (plan decision D-19).
   - The address is the authority: /investigations/:caseId/…, or ?case=<id> on global pages.
   - The investigation you last opened is remembered for this browser tab and offered as a choice;
     it is never applied silently. Evidence pages take their case from the evidence record. */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';

const KEY = 'nx-last-case';
type Ctx = {
  caseId: string | null;
  from: 'route' | 'query' | 'record' | null;
  lastCaseId: string | null;
  setScope: (caseId: string | null) => void;
  remember: (caseId: string) => void;
  /** a page whose record names its case (an evidence item) supplies it here while mounted */
  setRecordCase: (caseId: string | null) => void;
};
const CaseCtx = createContext<Ctx | null>(null);

const read = () => { try { return sessionStorage.getItem(KEY); } catch { return null; } };

export function CaseContextProvider({ children }: { children: ReactNode }) {
  const params = useParams<{ caseId?: string }>();
  const search = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const routeCase = params.caseId ? decodeURIComponent(params.caseId) : null;
  const queryCase = search.get('case');
  const [recordCase, setRecordCase] = useState<string | null>(null);
  const caseId = routeCase ?? queryCase ?? recordCase ?? null;
  const [lastCaseId, setLast] = useState<string | null>(null);

  const remember = useCallback((id: string) => {
    try { sessionStorage.setItem(KEY, id); } catch { /* storage unavailable: context still works from the address */ }
    setLast(id);
  }, []);
  useEffect(() => { setLast(read()); }, []);
  useEffect(() => { if (caseId) remember(caseId); }, [caseId, remember]);

  const setScope = useCallback((id: string | null) => {
    const next = new URLSearchParams(search.toString());
    if (id) next.set('case', id); else next.delete('case');
    const q = next.toString();
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }, [pathname, router, search]);

  const from = routeCase ? 'route' : queryCase ? 'query' : recordCase ? 'record' : null;
  return <CaseCtx.Provider value={{ caseId, from, lastCaseId, setScope, remember, setRecordCase }}>{children}</CaseCtx.Provider>;
}

export function useCaseContext() {
  const v = useContext(CaseCtx);
  if (!v) throw new Error('useCaseContext outside CaseContextProvider');
  return v;
}

/** Supply the case named by the record on screen (e.g. an evidence item's case) while mounted. */
export function useRecordCase(caseId: string | null | undefined) {
  const { setRecordCase } = useCaseContext();
  useEffect(() => {
    setRecordCase(caseId ?? null);
    return () => setRecordCase(null);
  }, [caseId, setRecordCase]);
}
