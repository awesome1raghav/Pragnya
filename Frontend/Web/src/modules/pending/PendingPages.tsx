'use client';

/* Application destinations whose backend modules are not built yet (Sources, Lineage, Graph, Reports). Each page states what it will show, which module provides it and when, keeps the
   investigation scope, and shows no sample records. */
import Link from 'next/link';
import s from '@/styles/workspace.module.css';
import CaseScope from '@/components/CaseScope';
import { PageHead, Unavailable } from '@/components/ui';
import { paths } from '@/config/routes';
import { useCaseContext } from '@/state/CaseContext';

export function SourcesPage() {
  return <div className={s.page}>
    <PageHead title='Sources' desc='Where a piece of media has been published, as far as permitted sources can show it.' />
    <CaseScope />
    <Unavailable title='Source intelligence' modules={['NEX-SRC']} step='plan Step 5'>
      <p>This page will list source records for the investigation: the URL, platform, publication time as stated by the source, when NEXTRON retrieved it and how, the evidence it produced, and similar media found in the searched scope.</p>
      <ul>
        <li>Sources enter by an investigator adding a URL; retrieval runs as a background job with safe URL handling.</li>
        <li>The earliest publication NEXTRON observes is shown as the earliest <em>observed</em>, never as the verified original.</li>
        <li>Discovery covers only the sources NEXTRON can reach, not the whole internet.</li>
      </ul>
    </Unavailable>
  </div>;
}

export function LineagePage() {
  return <div className={s.page}>
    <PageHead title='Lineage' desc='How versions of a piece of media relate: original-source candidates, derivatives and the transformations between them.' />
    <CaseScope />
    <Unavailable title='Media lineage' modules={['NEX-FPM', 'NEX-MOC', 'NEX-SRC', 'NEX-TRN']} step='plan Steps 5–6'>
      <p>The lineage graph needs fingerprints (NEX-FPM), relationships between versions (NEX-MOC, which also uses source records from NEX-SRC) and transformation hypotheses (NEX-TRN). Similarity will be shown as similarity, never as proof of common origin, and uncertain relationships will look different from supported ones.</p>
    </Unavailable>
  </div>;
}

export function GraphPage() {
  const { caseId } = useCaseContext();
  return <div className={s.page}>
    <PageHead title='Evidence graph' desc='Evidence, sources, findings and events of an investigation, and the relationships between them.' />
    <CaseScope />
    <Unavailable title='Evidence graph construction' modules={['NEX-EGC']} step='plan Step 7'>
      <p>Each edge in the graph will link to the stored observation that supports it, with its verification status. NEX-EGC builds the graph from source, lineage, transformation and correlation results, none of which exist yet, so no graph is drawn.</p>
      {caseId && <p>Until then, this investigation’s recorded history is on its <Link href={paths.caseTimeline(caseId)} style={{ textDecoration: 'underline' }}>timeline</Link>.</p>}
    </Unavailable>
  </div>;
}

export function ReportsPage() {
  const { caseId } = useCaseContext();
  return <div className={s.page}>
    <PageHead title='Reports' desc='Versioned investigation reports, traceable to evidence hashes, findings and reviews.' />
    <CaseScope />
    <Unavailable title='Reporting' modules={['NEX-RPT', 'NEX-INV']} step='plan Step 7'>
      <p>A report will freeze a snapshot of the investigation (evidence and their SHA-256, findings and their versions, reviews, contradictions and limitations) and render it as PDF and JSON with its own hash. Earlier versions stay available when a report is regenerated. No report can be generated until review exists.</p>
      {caseId && <p>The evidence and custody record a report will cite is already preserved; see <Link href={paths.caseEvidence(caseId)} style={{ textDecoration: 'underline' }}>this investigation’s evidence</Link>.</p>}
    </Unavailable>
  </div>;
}
