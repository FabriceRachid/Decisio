/**
 * Configuration des URLs et variables d'environnement
 */

// Default to same-origin `/api` so public tunnels can expose only the frontend.
// The Vite dev server already proxies `/api` to the local backend.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() || "";
export const API_VERSION = import.meta.env.VITE_API_VERSION || "v1";

export const API_ENDPOINTS = {
  // Auth
  auth: {
    register: "/api/auth/register/",
    login: "/api/auth/login/",
    logout: "/api/auth/logout/",
    refresh: "/api/auth/token/refresh/",
  },

  // KPI - M4
  kpi: {
    list: "/api/kpi/kpis/",
    autoList: "/api/kpi/auto/",
    autoDetect: "/api/kpi/auto/detect/",
    detail: (id: string) => `/api/kpi/kpis/${id}/`,
    calculate: (id: string) => `/api/kpi/kpis/${id}/calculate_now/`,
    history: (id: string) => `/api/kpi/kpis/${id}/history/`,
    anomalies: (id: string) => `/api/kpi/kpis/${id}/anomaly_detection/`,
    forecast: (id: string) => `/api/kpi/kpis/${id}/forecast/`,
    variance: (id: string) => `/api/kpi/kpis/${id}/variance_analysis/`,
    batchCalculate: "/api/kpi/kpis/batch_calculate/",
  },

  // KPI Alerts
  alerts: {
    list: "/api/kpi/alerts/",
    detail: (id: string) => `/api/kpi/alerts/${id}/`,
    create: "/api/kpi/alerts/",
    acknowledge: (id: string) => `/api/kpi/alerts/${id}/acknowledge/`,
    recentlyTriggered: "/api/kpi/alerts/triggered_recently/",
  },

  // Dashboard - M5
  dashboard: {
    preferences: "/api/dashboard/preferences/",
    preferencesReset: "/api/dashboard/preferences/reset/",
    views: "/api/dashboard/vues/",
    viewDetail: (id: string) => `/api/dashboard/vues/${id}/`,
    viewDefault: (id: string) => `/api/dashboard/vues/${id}/default/`,
    viewDuplicate: (id: string) => `/api/dashboard/vues/${id}/dupliquer/`,
    autoBuild: "/api/dashboard/auto-build/",
    addWidget: "/api/dashboard/add-widget/",
    widgets: "/api/dashboard/widgets/",
    widgetReorder: "/api/dashboard/widgets/reorder/",
  },

  // Workbench - M5
  workbench: {
    metric: "/api/kpi/workbench/metric/",
    pivot: "/api/kpi/workbench/pivot/",
    filters: "/api/kpi/filtres-disponibles/",
  },

  // Conflicts - M3
  conflicts: {
    list: "/api/conflits/conflicts/",
    resolve: (id: string) => `/api/conflits/conflicts/${id}/resolve/`,
  },

  // AI Interpretation - M6
  ia: {
    interpret: "/api/ia/interpret-kpis/",
    history: "/api/ia/history/",
    sourceKpis: (id: number) => `/api/ia/sources/${id}/kpis/`,
  },

  // Anomaly Detection - M7
  anomalies: {
    list: "/api/anomalies/detections/",
    detail: (id: number) => `/api/anomalies/detections/${id}/`,
    mlModels: "/api/anomalies/ml-models/",
    runIsolationForest: "/api/anomalies/isolation_forest/run/",
  },

  // Chatbot - M8
  chatbot: {
    sessions: "/api/chatbot/sessions/",
    sessionDetail: (id: number) => `/api/chatbot/sessions/${id}/`,
    messages: (id: number) => `/api/chatbot/sessions/${id}/messages/`,
  },

  // Reporting
  reports: {
    list: "/api/conflits/reports/",
    detail: (id: number) => `/api/conflits/reports/${id}/`,
    trigger: "/api/conflits/reports/trigger/",
    history: "/api/conflits/reports/history/",
    exportDashboard: "/api/dashboard/export/pdf/",
  },

  // Activity & Presence
  activity: {
    feed: "/api/conflits/activity-feed/",
  },
  presence: {
    heartbeat: "/api/conflits/presence/heartbeat/",
    list: "/api/conflits/presence/",
  },
};

export function getUrl(endpoint: string): string {
  return `${API_BASE_URL}${endpoint}`;
}
