import type { Metadata } from 'next';
import { CaseAnalysisScreen } from '@/modules/screens';
import type { AnalysisBranch } from '@/config/routes';

export const metadata: Metadata = { title: 'Analysis — NEXTRON' };

// only image, video, audio and provenance reach here; src/proxy.ts answers 404 for anything else
export default async function Page({ params }: { params: Promise<{ branch: string }> }) {
  return <CaseAnalysisScreen branch={(await params).branch as AnalysisBranch} />;
}
