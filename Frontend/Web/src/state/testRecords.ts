'use client';

/* Whether lists leave out the records automated tests, benchmarks and drills created ([E2E], [Bench], [Drill], [Test],
   [Smoke] titles). On by default, always announced with a count and a one-click "show", kept in this browser and followed
   by other tabs. It is a list filter only: nothing is changed or deleted. */
import { useCallback, useEffect, useState } from 'react';

const KEY = 'nx-hide-tests';

export function useHideTestRecords(): [boolean, (v: boolean) => void] {
  const [hide, setHide] = useState(true);
  useEffect(() => {
    const read = () => { try { setHide(localStorage.getItem(KEY) !== '0'); } catch { /* default */ } };
    read();
    window.addEventListener('storage', read);
    return () => window.removeEventListener('storage', read);
  }, []);
  const set = useCallback((v: boolean) => { setHide(v); try { localStorage.setItem(KEY, v ? '1' : '0'); } catch { /* storage unavailable */ } }, []);
  return [hide, set];
}
