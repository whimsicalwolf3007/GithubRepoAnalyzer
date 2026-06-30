import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Upload ──────────────────────────────────────────────
export const uploadExcel = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const uploadUrl = (url) => api.post('/upload/url', { url });

export const getBatchStatus = (batchId) => api.get(`/upload/${batchId}/status`);

// ── Repositories ──────────────────────────────────────────
export const getRepositories = (params = {}) => api.get('/repositories', { params });

export const getRepository = (id) => api.get(`/repositories/${id}`);

export const deleteRepository = (id) => api.delete(`/repositories/${id}`);

export const generateAutoFix = (recId) => api.post(`/recommendations/${recId}/auto-fix`);

// ── Analysis ──────────────────────────────────────────────
export const triggerAnalysis = (repoId, force = true) => api.post(`/analyze/${repoId}?force=${force}`);

export const triggerBatchAnalysis = (batchId) => api.post(`/analyze/batch/${batchId}`);

export const analyzeUrl = (url) => api.post('/analyze/url', { url });

export const getAnalysisStatus = (repoId) => api.get(`/analyze/${repoId}/status`);

// ── Dashboard ──────────────────────────────────────────────
export const getDashboardStats = () => api.get('/dashboard/stats');

export const getTechDistribution = () => api.get('/dashboard/tech-distribution');

export const getFeasibilityOverview = () => api.get('/dashboard/feasibility-overview');

export const getRecentActivity = (limit = 10) =>
  api.get('/dashboard/recent-activity', { params: { limit } });

// ── Reports ──────────────────────────────────────────────
export const downloadExcelReport = () =>
  api.get('/reports/excel', { responseType: 'blob' });

export const downloadJsonReport = () => api.get('/reports/json');

// ── Health ──────────────────────────────────────────────
export const healthCheck = () => api.get('/health');

export default api;
