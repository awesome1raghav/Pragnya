import Landing from '@/modules/landing/Landing';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'NEXTRON — Seeing isn’t believing',
  description: 'Investigate manipulated media and find the evidence, frame by frame: spatial, temporal and audio-visual analysis in one record.',
  other: { 'page-type': 'software', 'site-kind': 'software' },
  openGraph: {
    title: 'NEXTRON — Seeing isn’t believing',
    description: 'Spatial, temporal and audio-visual checks on MP4, MOV and WebM, each finding marked at its timestamp and region.',
    type: 'website',
    images: ['/images/forensic-portrait.png'],
  },
};

export default function Page() { return <Landing />; }
