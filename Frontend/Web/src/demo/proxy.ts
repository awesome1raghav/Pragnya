/* Unknown investigation and report IDs, and unknown analysis types, answer with a real 404 status. Rendering streams its first byte with a
   200, so the check has to happen here, before rendering. With the demo data the IDs are known up front; once
   NEXT_PUBLIC_NEXTRON_API points at the backend, this steps aside and each page reports a missing ID itself. */
import { NextResponse, type NextRequest } from 'next/server';
import { cases } from '@/demo/api/fixtures';

const IDS = new Set(cases.map(c => c.id));
const LISTS = new Set(['new', 'active', 'completed', 'archived']);
const BRANCHES = new Set(['image', 'video', 'audio', 'provenance']);

export function proxy(request: NextRequest) {
  const [, section, id, tab, branch] = request.nextUrl.pathname.split('/');
  const badBranch = section === 'investigations' && tab === 'analysis' && branch !== undefined && !BRANCHES.has(branch);
  if (badBranch) return NextResponse.rewrite(new URL('/not-found', request.url));
  if (process.env.NEXT_PUBLIC_NEXTRON_API) return NextResponse.next();
  const known = !id || (section === 'investigations' && LISTS.has(id)) || IDS.has(decodeURIComponent(id));
  return known ? NextResponse.next() : NextResponse.rewrite(new URL('/not-found', request.url));
}

export const config = { matcher: ['/investigations/:id/:path*', '/reports/:id/:path*'] };
