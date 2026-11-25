'use client';

/* Route pages are server components (they own the address, the title and 404s); each renders one of these,
   which connects a module to the workspace shell's context. */
import { useWorkspace } from '@/layouts/MainLayout';
import Dashboard from './dashboard/Dashboard';
import InvestigationList, { type CaseFilter } from './investigations/InvestigationList';
import NewInvestigation from './investigations/NewInvestigation';
import { CaseAnalysis, CaseEvents, CaseEvidence, CaseOverview, CaseReview, CaseTimeline } from './investigations/CasePages';
import { EvidenceList, Integrity } from './evidence/EvidencePages';
import EvidenceGraph from './evidence-graph/EvidenceGraph';
import { Report } from './reports/ReportStudio';
import ReportList from './reports/ReportList';
import Notifications from './notifications/Notifications';
import { Audit } from './system/Governance';
import Settings from './settings/Settings';
import type { AnalysisBranch } from '@/config/routes';

export const DashboardScreen = () => <Dashboard {...useWorkspace()} />;
export const InvestigationsScreen = ({ filter }: { filter?: CaseFilter }) => <InvestigationList filter={filter} />;
export const NewInvestigationScreen = () => <NewInvestigation {...useWorkspace()} />;
export const CaseOverviewScreen = () => <CaseOverview {...useWorkspace()} />;
export const CaseEvidenceScreen = () => <CaseEvidence {...useWorkspace()} />;
export const CaseAnalysisScreen = ({ branch }: { branch?: AnalysisBranch }) => <CaseAnalysis {...useWorkspace()} branch={branch} />;
export const CaseTimelineScreen = () => <CaseTimeline {...useWorkspace()} />;
export const CaseReviewScreen = () => <CaseReview {...useWorkspace()} />;
export const CaseEventsScreen = () => <CaseEvents {...useWorkspace()} />;
export const EvidenceListScreen = () => <EvidenceList />;
export const IntegrityScreen = () => <Integrity {...useWorkspace()} />;
export const GraphScreen = () => <EvidenceGraph {...useWorkspace()} />;
export const ReportListScreen = () => <ReportList />;
export const ReportScreen = ({ preview }: { preview?: boolean }) => <Report {...useWorkspace()} previewOnly={preview} />;
export const NotificationsScreen = () => <Notifications {...useWorkspace()} />;
export const SystemScreen = ({ section }: { section?: 'all' | 'health' | 'logs' }) => <Audit {...useWorkspace()} section={section} />;
export const SettingsScreen = () => <Settings {...useWorkspace()} />;
