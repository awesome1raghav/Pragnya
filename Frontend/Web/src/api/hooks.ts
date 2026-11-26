'use client';

/* Typed read hooks over the query cache. Keys are namespaced so writes can invalidate precisely:
   'cases'… (lists and statistics), 'case:<id>'… (one investigation), 'evidence'…, 'ev:<id>'…, 'system'…,
   'jobs'… (job lists), 'run:<id>' (one run), 'notifications'…. Live events invalidate them (api/live.tsx). */
import { api, type CaseQuery, type EvidenceQuery, type JobQuery } from '@/api';
import { useQuery } from './query';

const k = (o: object) => JSON.stringify(o);

export const useCases = (q: CaseQuery) => useQuery(`cases:list:${k(q)}`, () => api.cases.list(q));
export const useCaseStatistics = () => useQuery('cases:stats', api.cases.statistics);
export const useCase = (id: string | null) => useQuery(id ? `case:${id}` : null, () => api.cases.get(id!));
export const useCaseSummary = (id: string | null) => useQuery(id ? `case:${id}:summary` : null, () => api.cases.summary(id!));
export const useCaseEvidence = (id: string | null) => useQuery(id ? `case:${id}:evidence` : null, () => api.evidence.listForCase(id!));

export const useEvidenceList = (q: EvidenceQuery) => useQuery(`evidence:list:${k(q)}`, () => api.evidence.list(q));
export const useEvidenceStatistics = () => useQuery('evidence:stats', api.evidence.statistics);
export const useEvidence = (id: string | null) => useQuery(id ? `ev:${id}` : null, () => api.evidence.get(id!));
export const useMetadata = (id: string | null) => useQuery(id ? `ev:${id}:metadata` : null, () => api.evidence.metadata(id!));
export const useIntegrity = (id: string | null) => useQuery(id ? `ev:${id}:integrity` : null, () => api.evidence.integrity(id!));

export const useLiveness = () => useQuery('system:health', api.system.health, { refreshMs: 30_000 });
export const useReadiness = () => useQuery('system:ready', api.system.ready, { refreshMs: 15_000 });
export const useDatabaseStatus = () => useQuery('system:database', api.system.database);
export const useStorageStatus = () => useQuery('system:storage', api.system.storage);
export const useModules = () => useQuery('system:modules', api.system.modules);
export const useWorkers = () => useQuery('system:workers', api.system.workers, { refreshMs: 15_000 });
export const useSystemConfig = () => useQuery('system:config', api.system.config);
export const usePreferences = () => useQuery('preferences', api.preferences.get);

export const useJobs = (q: JobQuery = {}) => useQuery(`jobs:list:${k(q)}`, () => api.jobs.list(q));
export const useRun = (jobId: string | null) => useQuery(jobId ? `run:${jobId}` : null, () => api.runs.get(jobId!));
export const useCaseRuns = (caseId: string | null) => useQuery(caseId ? `jobs:case:${caseId}` : null, () => api.runs.list(caseId!));
export const useModuleResults = (caseId: string | null, moduleId: string) => useQuery(caseId ? `case:${caseId}:module:${moduleId}` : null, () => api.analysis.moduleResults(caseId!, moduleId));
export const useEvidenceAnalysis = (id: string | null) => useQuery(id ? `ev:${id}:analysis` : null, () => api.analysis.forEvidence(id!));
export const useSources = (caseId: string | null) => useQuery(`sources:${caseId ?? 'all'}`, () => api.sources.list(caseId));
export const useSourceHistory = (id: string | null) => useQuery(id ? `sources:history:${id}` : null, () => api.sources.history(id!));
export const useConnectors = () => useQuery('sources:connectors', api.sources.connectors);
export const useLineage = (caseId: string | null) => useQuery(caseId ? `case:${caseId}:lineage` : null, () => api.lineage(caseId!));
export const useNotifications = (unread: boolean) => useQuery(`notifications:list:${unread}`, () => api.notifications.list(unread));
export const useNotificationSummary = () => useQuery('notifications:summary', api.notifications.summary, { refreshMs: 60_000 });
export const useGraph = (caseId: string | null) => useQuery(caseId ? `case:${caseId}:graph` : null, () => api.graph(caseId!));
export const useReconstruction = (caseId: string | null) => useQuery(caseId ? `case:${caseId}:reconstruction` : null, () => api.reconstruction(caseId!));
export const useReviews = (caseId: string | null, current = false) => useQuery(caseId ? `case:${caseId}:reviews:${current}` : null, () => api.reviews.list(caseId!, current));
export const useReports = (caseId: string | null) => useQuery(caseId ? `case:${caseId}:reports` : null, () => api.reports.list(caseId!));
