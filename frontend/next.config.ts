import type { NextConfig } from 'next';

const config: NextConfig = {
  // the old single-page workspace address keeps working for bookmarks
  async redirects() {
    return [{ source: '/workspace', destination: '/dashboard', permanent: false }];
  },
};

export default config;
