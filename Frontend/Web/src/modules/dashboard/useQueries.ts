'use client';

/* Up to five cached reads at once, built on the same cache as useQuery. Hooks need a fixed count,
   so five slots are always called and unused slots get a null key (which fetches nothing). */
import { useQuery, type QueryResult } from '@/api/query';

const MAX = 5;
const unused = () => Promise.reject(new Error('unused query slot'));

export function useQueries<T>(specs: { key: string; fn: () => Promise<T> }[]): QueryResult<T>[] {
  const results: QueryResult<T>[] = [];
  for (let i = 0; i < MAX; i++) {
    const spec = specs[i];
    // eslint-disable-next-line react-hooks/rules-of-hooks -- fixed number of calls per render
    results.push(useQuery<T>(spec?.key ?? null, spec?.fn ?? unused));
  }
  return results.slice(0, Math.min(specs.length, MAX));
}
