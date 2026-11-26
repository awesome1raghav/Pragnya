'use client';

/* Route pages are server components (they own the address and the title); each renders one of these
   client screens, which loads its own data from the API. */
import Dashboard from './dashboard/Dashboard';
import InvestigationList from './investigations/InvestigationList';
import NewInvestigation from './investigations/NewInvestigation';
import { CaseAddEvidence, CaseEvents, CaseEvidence, CaseOverview, CasePending, CaseTimeline } from './investigations/CasePages';
import EvidenceList from './evidence/EvidenceList';
import { EvidenceAnalysis, EvidenceIntegrity, EvidenceMetadata, EvidenceOverview, EvidencePreview, EvidenceTimeline } from './evidence/EvidencePages';
import Intelligence from './intelligence/Intelligence';
import { GraphPage, LineagePage, ReportsPage, SourcesPage } from './pending/PendingPages';
import NotificationsPage from './notifications/Notifications';
import { SystemHealth, SystemLogs, SystemOverview } from './system/SystemPages';
import Settings from './settings/Settings';
import type { AnalysisBranch, CaseFilter } from '@/config/routes';

export const DashboardScreen = () => <Dashboard />;
export const InvestigationsScreen = ({ filter }: { filter?: CaseFilter }) => <InvestigationList filter={filter} />;
export const NewInvestigationScreen = () => <NewInvestigation />;
export const CaseOverviewScreen = () => <CaseOverview />;
export const CaseEvidenceScreen = () => <CaseEvidence />;
export const CaseAddEvidenceScreen = () => <CaseAddEvidence />;
export const CaseTimelineScreen = () => <CaseTimeline />;
export const CaseEventsScreen = () => <CaseEvents />;
export const CasePendingScreen = ({ kind, branch }: { kind: 'analysis' | 'graph' | 'review' | 'report'; branch?: AnalysisBranch }) => <CasePending kind={kind} branch={branch} />;
export const EvidenceListScreen = () => <EvidenceList />;
export const EvidenceOverviewScreen = () => <EvidenceOverview />;
export const EvidencePreviewScreen = () => <EvidencePreview />;
export const EvidenceMetadataScreen = () => <EvidenceMetadata />;
export const EvidenceIntegrityScreen = () => <EvidenceIntegrity />;
export const EvidenceTimelineScreen = () => <EvidenceTimeline />;
export const EvidenceAnalysisScreen = () => <EvidenceAnalysis />;
export const SourcesScreen = () => <SourcesPage />;
export const LineageScreen = () => <LineagePage />;
export const IntelligenceScreen = () => <Intelligence />;
export const GraphScreen = () => <GraphPage />;
export const ReportsScreen = () => <ReportsPage />;
export const NotificationsScreen = () => <NotificationsPage />;
export const SystemScreen = () => <SystemOverview />;
export const SystemHealthScreen = () => <SystemHealth />;
export const SystemLogsScreen = () => <SystemLogs />;
export const SettingsScreen = () => <Settings />;
