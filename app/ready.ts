/* The entry loader flips <html data-nx-ready="1"> and fires `nx:ready` when it hands the page over.
   Anything that should start with the reveal (the hero intro, the console's analysis run) waits here. */
export const isReady = () => typeof document !== 'undefined' && document.documentElement.dataset.nxReady === '1';

export function whenReady(cb: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  if (isReady()) { cb(); return () => {}; }
  const h = () => cb();
  window.addEventListener('nx:ready', h, { once: true });
  return () => window.removeEventListener('nx:ready', h);
}
