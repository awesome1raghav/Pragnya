import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { CasePendingScreen } from '@/modules/screens';
import { ANALYSIS_BRANCHES, ANALYSIS_LABEL, type AnalysisBranch } from '@/config/routes';

const isBranch = (b: string): b is AnalysisBranch => (ANALYSIS_BRANCHES as readonly string[]).includes(b);

export async function generateMetadata({ params }: { params: Promise<{ branch: string }> }): Promise<Metadata> {
  const { branch } = await params;
  return { title: `${isBranch(branch) ? ANALYSIS_LABEL[branch] : 'Unknown'} analysis — NEXTRON` };
}

export default async function Page({ params }: { params: Promise<{ branch: string }> }) {
  const { branch } = await params;
  if (!isBranch(branch)) notFound();
  return <CasePendingScreen kind='analysis' branch={branch} />;
}
