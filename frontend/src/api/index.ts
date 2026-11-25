/* Which adapter the app talks to:
   - NEXT_PUBLIC_NEXTRON_API unset  → the in-memory mock (demo data, works offline)
   - NEXT_PUBLIC_NEXTRON_API=https://api.example → the real backend over HTTP */
import { httpApi } from './client';
import { mockApi } from './mock';
import type { NextronApi } from './contract';

const base = process.env.NEXT_PUBLIC_NEXTRON_API;
export const api: NextronApi = base
  ? httpApi(base, () => { try { return localStorage.getItem('nx-token'); } catch { return null; } })
  : mockApi;
export const usingMock = !base;
export * from './contract';
