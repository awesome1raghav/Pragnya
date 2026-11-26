/* Addresses that cannot exist answer with a real HTTP 404. Rendering streams its first byte with a 200,
   so these checks must run here, before rendering:
   - an analysis type other than image, video, audio or provenance;
   - any report address (no report records exist until NEX-RPT is built, plan Step 7);
   - a malformed investigation or evidence ID (IDs are UUIDs).
   Well-formed IDs that do not exist are reported by the page itself, after asking the API. */
import { NextResponse, type NextRequest } from 'next/server';

const BRANCHES = new Set(['image', 'video', 'audio', 'provenance']);
const LISTS = new Set(['new', 'active', 'completed', 'archived']);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function proxy(request: NextRequest) {
  const [, section, id, tab, branch] = request.nextUrl.pathname.split('/');
  const notFound = () => NextResponse.rewrite(new URL('/not-found', request.url), { status: 404 });
  if (section === 'reports' && id) return notFound();
  if (section === 'investigations' && id && !LISTS.has(id) && !UUID.test(decodeURIComponent(id))) return notFound();
  if (section === 'evidence' && id && !UUID.test(decodeURIComponent(id))) return notFound();
  if (section === 'investigations' && tab === 'analysis' && branch !== undefined && !BRANCHES.has(branch)) return notFound();
  return NextResponse.next();
}

export const config = { matcher: ['/investigations/:id/:path*', '/evidence/:id/:path*', '/reports/:id/:path*'] };
