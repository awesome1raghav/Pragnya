import type { NextConfig } from 'next';

const config: NextConfig = {
  async redirects() {
    return [
      // `/` is the landing page again (operator request, 26 Nov 2026; reverses default D-1). It is also at /about.
      // the old single-page workspace address keeps working for bookmarks
      { source: '/workspace', destination: '/dashboard', permanent: false },
    ];
  },
};

export default config;
