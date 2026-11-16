/**
 * Client API pour DécisioBI
 * Gère tous les appels au backend avec gestion d'erreurs et authentification
 */

import { API_ENDPOINTS, getUrl } from "./env";
import { toast } from "./toast";

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Types pour les KPIs
export interface KPI {
  id: number;
  code: string;
  name: string;
  description?: string;
  target_value?: number;
  frequency: string;
  category: string;
  unit: string;
  is_active: boolean;
  is_public: boolean;
  last_calculated_at?: string;
}

export interface KPICalculation {
  id: number;
  kpi: number;
  period_label: string;
  period_start: string;
  period_end: string;
  calculated_value: number;
  previous_value?: number;
  variance_absolute?: number;
  variance_percent?: number;
  status: "on_target" | "warning" | "critical";
  breakdown?: Record<string, number>;
  anomaly_detected: boolean;
  data_quality_score?: number;
  rows_processed?: number;
}

export type KPIAlertType = "threshold_breach" | "anomaly" | "scheduled";
export type KPIAlertCondition = "above" | "below" | "equals" | "changed_by";
export type KPIAlertChannel = "email" | "webhook";

/** Élément de liste — KPIAlertListSerializer. */
export interface KPIAlert {
  id: number;
  alert_name: string;
  kpi_name?: string;
  kpi_code?: string;
  alert_type: KPIAlertType;
  condition_type: KPIAlertCondition;
  threshold_value: string | number | null;
  threshold_percent?: string | number | null;
  is_active: boolean;
  is_triggered: boolean;
  last_triggered_at: string | null;
  acknowledged_at?: string | null;
  trigger_count: number;
  created_by_name?: string;
  created_at: string;
}

/** Configuration complète — KPIAlertDetailSerializer. */
export interface KPIAlertDetail {
  id: number;
  kpi_detail?: { id: number; name: string; code: string; unit?: string };
  alert_name: string;
  alert_type: KPIAlertType;
  condition_type: KPIAlertCondition;
  threshold_value: string | number | null;
  threshold_percent: string | number | null;
  notification_channels: string[];
  recipients: string[];
  webhook_url?: string | null;
  message_template?: string | null;
  is_active: boolean;
  is_triggered: boolean;
  trigger_count: number;
  last_triggered_at: string | null;
  last_value: string | number | null;
  cooldown_minutes: number;
  mute_until?: string | null;
  acknowledged_at?: string | null;
  resolution_notes?: string | null;
  created_at: string;
  updated_at: string;
}

/** Corps d'écriture — KPIAlertCreateUpdateSerializer. */
export interface KPIAlertPayload {
  kpi: number;
  alert_name: string;
  alert_type: KPIAlertType;
  condition_type: KPIAlertCondition;
  threshold_value: number | null;
  threshold_percent: number | null;
  notification_channels: KPIAlertChannel[];
  recipients: string[];
  webhook_url: string | null;
  message_template: string | null;
  is_active: boolean;
  cooldown_minutes: number;
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  date_joined?: string;
  last_login?: string | null;
  profile: {
    id: number;
    role: "admin" | "analyst" | "viewer";
    role_display?: string;
    department?: string;
    phone_number?: string;
    avatar_url?: string;
    timezone?: string;
    language?: string;
    mfa_enabled?: boolean;
    is_email_verified?: boolean;
    last_password_change?: string | null;
    failed_login_attempts?: number;
    locked_until?: string | null;
    password_expires_at?: string | null;
  };
}

export interface KPIAnomaly {
  has_anomaly: boolean;
  z_score: number;
  mean: number;
  std_dev: number;
  confidence: number;
  anomaly_reason?: string;
}

export interface KPIForecast {
  forecast_value: number;
  confidence_interval: [number, number];
  trend: "upward" | "downward" | "stable";
  trend_strength: number;
  forecast_accuracy: number;
}

export interface DetectedColumn {
  name: string;
  type: "numeric" | "categorical" | "date" | "id";
  samples: unknown[];
  null_ratio: number;
  unique_ratio: number;
}

export interface MetricSuggestion {
  label: string;
  measure_column: string;
  aggregation: string;
  description: string;
}

export interface AutoKPIDetectResponse {
  source_id: number;
  source_name: string;
  domain_profile: {
    domain: string;
    confidence: string;
    matched_signals: Record<string, string[]>;
    scores: Record<string, number>;
  };
  columns: {
    numeric: DetectedColumn[];
    categorical: DetectedColumn[];
    date: DetectedColumn[];
    id: DetectedColumn[];
  };
  suggestions: MetricSuggestion[];
  period_label: string;
}

// Types pour les préférences et vues
export interface UserPreference {
  id: number;
  user: number;
  colonnes_tableau: string[];
  kpis_visibles: string[];
  kpis_ordre: string[];
  layout_dashboard: Record<string, any>;
  periode_defaut: string;
  devise: string;
  format_nombres: string;
}

export interface SavedView {
  id: number;
  user: number;
  nom: string;
  description?: string;
  icone: string;
  config: Record<string, any>;
  is_default: boolean;
  is_partagee: boolean;
  ordre: number;
  created_at: string;
}

export interface ImportTemplate {
  id: string;
  name: string;
  description?: string;
  source_type?: string;
  required_columns?: string[];
  key_columns?: string[];
}

export interface ValidationMessage {
  code: string;
  message: string;
}

export interface PreviewValidationError {
  code: string;
  message: string;
  severity: "error" | "warning" | "info";
}

export interface PreviewRowValidation {
  row_number: number;
  data: Record<string, unknown>;
  status: string;
  messages: ValidationMessage[];
}

export interface IngestionPreviewResponse {
  filename: string;
  source_type: string;
  delimiter: string;
  encoding: string;
  checksum_md5: string;
  file_size_bytes: number;
  row_count: number;
  column_count: number;
  rows: Record<string, unknown>[];
  columns: string[];
  metadata?: Record<string, unknown>;
  validation_errors: PreviewValidationError[];
  row_validation_results: PreviewRowValidation[];
  sample_rows?: PreviewRowValidation[];
  can_import: boolean;
  multi_sheet?: boolean;
  sheet_count?: number;
  sheets?: Array<{
    sheet_name: string;
    row_count: number;
    column_count: number;
    columns: string[];
    rows: Record<string, unknown>[];
    quality_score?: number;
    content_type?: string;
    validation_errors: PreviewValidationError[];
    row_validation_results: PreviewRowValidation[];
  }>;
}

export interface DataSourceDetail {
  id: number;
  name: string;
  source_type: string;
  status: string;
  file_path?: string;
  file_size_bytes: number;
  row_count: number;
  column_count: number;
  delimiter?: string;
  encoding?: string;
  has_header?: boolean;
  validation_errors?: PreviewValidationError[];
  metadata?: Record<string, any>;
  checksum_md5?: string;
  retention_days?: number;
  is_archived?: boolean;
  description?: string;
  tags?: string[];
  schema_version?: string;
  lineage_info?: Record<string, any> | null;
  uploaded_by?: number;
  uploaded_by_username?: string;
  created_at?: string;
  updated_at?: string;
  processed_at?: string | null;
  sample_rows?: Array<{
    row_number: number;
    data: Record<string, unknown>;
    validation_status: string;
    validation_messages: any[];
  }>;
  sheets?: Array<{
    id: number;
    sheet_name: string;
    sheet_index: number;
    row_count: number;
    column_count: number;
    column_names: string[];
    is_active: boolean;
    quality_score?: number;
    content_type?: string;
    metadata?: Record<string, any>;
  }>;
}

export interface SheetRelation {
  id: number;
  relation_name: string;
  from_sheet: string;
  from_column: string;
  to_sheet: string;
  to_column: string;
  join_type: string;
  is_active: boolean;
  confidence: number;
  match_ratio: number;
  created_by?: number;
  created_by_username?: string;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface RelationSuggestion {
  from_sheet: string;
  from_column: string;
  to_sheet: string;
  to_column: string;
  confidence: number;
  match_ratio: number;
  reason: string;
}

export interface JoinedViewResponse {
  columns: string[];
  rows: Record<string, any>[];
  relations_used: string[];
  join_stats: Record<string, any>;
  total_rows?: number;
}

export interface IngestionJob {
  id: number;
  celery_task_id?: string | null;
  requested_by?: number;
  requested_by_username?: string;
  status: string;
  progress_percent?: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string;
  source?: number | null;
  source_detail?: DataSourceDetail | null;
}

export interface CleaningSuggestion {
  alertes?: Array<Record<string, any>>;
  corrections?: Array<Record<string, any>>;
  recommended_pipeline?: {
    id: number;
    name?: string;
    description?: string;
  } | null;
  [key: string]: any;
}

export interface CleaningPreviewResponse {
  summary: {
    rows_affected?: number;
    rows_removed?: number;
    columns_removed?: number;
    [key: string]: any;
  };
  cleaning_report?: Record<string, any>;
  orchestration?: Record<string, any>;
  [key: string]: any;
}

export interface CleaningJobResponse {
  id: number;
  source?: number;
  source_id?: number;
  source_name?: string;
  status: string;
  progress_percent?: number;
  validated_rows?: number;
  pending_rows?: number;
  is_fully_validated?: boolean;
  result_job_id?: number | null;
  error_message?: string | null;
  export_path?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  validation_status?: string;
  [key: string]: any;
}

export interface CleaningJobDetail {
  job: CleaningJobResponse & {
    execution_context?: Record<string, any>;
    orchestration?: Record<string, any>;
  };
  preview_rows?: Array<Record<string, any>>;
  [key: string]: any;
}

export interface CleaningComparison {
  rows?: Array<Record<string, any>>;
  before_columns?: string[];
  before_rows_preview?: Array<Record<string, any>>;
  after_columns?: string[];
  after_rows_preview?: Array<Record<string, any>>;
  changes_by_type?: Record<string, number>;
  structure_reconstruction?: Record<string, any> | null;
  orchestration?: Record<string, any>;
  [key: string]: any;
}

// Types M6 — Interprétation IA
export interface AIInterpretationResponse {
  interpretation: string;
  model: string;
  tokens_used: number | null;
  processing_time_ms: number | null;
  kpi_count: number;
  analysis_id: number | null;
}

export interface AIHistoryItem {
  id: number;
  prompt: string;
  response: string;
  model: string;
  tokens_used: number | null;
  processing_time_ms: number | null;
  status: string;
  kpi_count: number;
  created_at: string | null;
}

export interface AIHistoryResponse {
  count: number;
  page: number;
  page_size: number;
  results: AIHistoryItem[];
}

export interface SourceKPI {
  widget_id: number;
  title: string;
  measure: string;
  aggregation: string;
  group_by: string[];
  value: number;
  formatted_value: string;
  rows_processed: number;
  breakdown: any[];
  chart_type: string;
  semantic_type: string;
}

export interface SourceKPIsResponse {
  source_id: number;
  kpis: SourceKPI[];
}

// M7 — Anomaly Detection
export interface AnomalyDetection {
  id: number;
  data_source: number;
  data_source_name: string;
  model: number;
  model_name: string;
  algorithm: string;
  anomaly_score: number;
  severity: "critique" | "moyen" | "faible";
  status: "new" | "investigating" | "confirmed" | "false_positive" | "resolved";
  confidence: number;
  outlier_count: number;
  detected_at: string;
}

export interface AnomalyDetail extends AnomalyDetection {
  row_ids: number[];
  affected_columns: string[];
  contribution_scores: Record<string, number>;
  explanation: string;
  anomaly_type: string;
  pattern_description: string;
  is_reviewed: boolean;
  review_notes: string;
}

export interface AnomalyListResponse {
  count: number;
  results: AnomalyDetection[];
}

export interface AnomalyStatusUpdate {
  status?: "new" | "investigating" | "confirmed" | "false_positive" | "resolved";
  is_reviewed?: boolean;
  review_notes?: string;
}

export interface IsolationForestRunRequest {
  source_id: number;
  feature_columns: string[];
  backend?: "raw" | "cleaned";
  contamination?: number;
  max_rows?: number;
  persist?: boolean;
  model_name?: string;
}

export interface IsolationForestResult {
  source_id: number;
  source_name: string;
  backend: string;
  feature_columns: string[];
  n_samples: number;
  n_features: number;
  contamination_requested: number;
  contamination_effective: number;
  outlier_count: number;
  outlier_row_numbers: number[];
  col_medians?: Record<string, number>;
  outlier_details?: Array<{
    row_number: number;
    deviations: Array<{
      column: string;
      valeur: number;
      mediane: number;
      ratio: number;
      direction: string;
    }>;
  }>;
  rows: Array<{ row_number: number; score: number; is_outlier: boolean }>;
  persisted?: { anomaly_model_id: number; anomaly_id: number };
}

// M8 — Chatbot
export interface ChatSession {
  id: number;
  session_token: string;
  session_name: string | null;
  bot_personality: string;
  message_count: number;
  is_active: boolean;
  started_at: string;
  last_activity_at: string;
  tags: string[];
}

export interface ChatMessage {
  id: number;
  message_type: "user" | "bot" | "system";
  content_type: string;
  content: string;
  intent: string;
  sentiment: string;
  confidence: number;
  attached_data: Record<string, any> | null;
  suggested_questions: string[] | null;
  response_time_ms: number | null;
  model_used: string | null;
  fallback_used: boolean;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  context: Record<string, any>;
  active_kpis: number[];
}

// Classe client API
export class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl = getUrl("")) {
    this.baseUrl = baseUrl;
    this.token = this.getStoredToken();
  }

  private getStoredToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("auth_token");
  }

  private setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("auth_token", token);
    } else {
      localStorage.removeItem("auth_token");
    }
  }

  setAuthToken(token: string | null) {
    this.setToken(token);
  }

  getAuthToken(): string | null {
    return this.token;
  }

  async login(
    username: string,
    password: string,
  ): Promise<{ access_token: string; refresh_token: string; user?: any }> {
    const response = await fetch(getUrl(API_ENDPOINTS.auth.login), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw {
        status: response.status,
        message: data.error || data.detail || data.message || response.statusText,
        data,
      };
    }

    const accessToken = data.access_token || data.access;
    const refreshToken = data.refresh_token || data.refresh;

    if (accessToken) {
      this.setToken(accessToken);
    }

    if (refreshToken) {
      localStorage.setItem("refresh_token", refreshToken);
    }

    return data;
  }

  async register(data: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name?: string;
    last_name?: string;
    company_name?: string;
    company_sector?: string;
    company_size?: string;
    company_country?: string;
  }): Promise<{ message: string; user: AuthUser; access_token: string; refresh_token: string }> {
    const response = await fetch(getUrl(API_ENDPOINTS.auth.register), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const responseData = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw {
        status: response.status,
        message:
          responseData.error || responseData.detail || responseData.message || response.statusText,
        data: responseData,
      };
    }

    if (responseData.access_token) {
      this.setToken(responseData.access_token);
    }

    if (responseData.refresh_token) {
      localStorage.setItem("refresh_token", responseData.refresh_token);
    }

    return responseData;
  }

  async getProfile(): Promise<{
    id: number;
    username: string;
    email: string;
    first_name?: string;
    last_name?: string;
    date_joined?: string;
    last_login?: string;
    profile?: any;
  }> {
    return this.request("GET", "/api/auth/profile/");
  }

  async updateProfile(data: {
    username?: string;
    email?: string;
    first_name?: string;
    last_name?: string;
    profile?: Record<string, any>;
  }): Promise<any> {
    return this.request("PUT", "/api/auth/profile/", data);
  }

  async getOrganization(): Promise<any> {
    return this.request("GET", "/api/auth/organization/");
  }

  async updateOrganization(data: {
    name?: string;
    brand_color?: string;
    logo?: File | null;
  }): Promise<any> {
    const form = new FormData();
    if (data.name !== undefined) form.append("name", data.name);
    if (data.brand_color !== undefined) form.append("brand_color", data.brand_color);
    if (data.logo !== undefined && data.logo !== null) form.append("logo", data.logo);
    const url = `${this.baseUrl}/api/auth/organization/`;
    const headers: HeadersInit = {};
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const response = await fetch(url, { method: "PATCH", headers, body: form });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.detail || errorData.message || response.statusText,
        data: errorData,
      };
    }
    return response.json();
  }

  async getAdminUsers(): Promise<AdminUser[]> {
    const response = await this.request<{ results?: AdminUser[] } | AdminUser[]>(
      "GET",
      "/api/auth/admin/users/",
    );
    return Array.isArray(response) ? response : response.results || [];
  }

  async createAdminUser(data: {
    username: string;
    email: string;
    password?: string;
    first_name?: string;
    last_name?: string;
    role: "admin" | "analyst" | "viewer";
  }): Promise<AdminUser> {
    return this.request("POST", "/api/auth/admin/users/", data);
  }

  async updateAdminUserRole(userId: number, role: "admin" | "analyst" | "viewer"): Promise<any> {
    return this.request("POST", `/api/auth/admin/users/${userId}/update-role/`, { role });
  }

  async updateAdminUser(
    userId: number,
    data: {
      username?: string;
      email?: string;
      first_name?: string;
      last_name?: string;
      is_active?: boolean;
      profile?: {
        role?: "admin" | "analyst" | "viewer";
        department?: string;
        phone_number?: string;
        timezone?: string;
        language?: string;
      };
    },
  ): Promise<AdminUser> {
    return this.request("PUT", `/api/auth/admin/users/${userId}/`, data);
  }

  async deleteAdminUser(userId: number): Promise<void> {
    return this.request("DELETE", `/api/auth/admin/users/${userId}/`);
  }

  logout() {
    this.setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("refresh_token");
    }
  }

  private async request<T>(
    method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH",
    endpoint: string,
    data?: any,
    options?: { contentType?: string },
  ): Promise<T> {
    const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint}`;

    const headers: HeadersInit = {
      "Content-Type": options?.contentType || "application/json",
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const config: RequestInit = {
      method,
      headers,
    };

    if (data && (method === "POST" || method === "PUT" || method === "PATCH")) {
      if (data instanceof FormData) {
        delete headers["Content-Type"];
        config.body = data;
      } else {
        config.body = JSON.stringify(data);
      }
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw {
          status: response.status,
          message: errorData.detail || errorData.message || response.statusText,
          data: errorData,
        };
      }

      if (response.status === 204) {
        return {} as T;
      }

      return await response.json();
    } catch (error: any) {
      console.error(`API Error [${method} ${url}]:`, error);

      if (error.status === 401) {
        this.setToken(null);
        window.location.href = "/login";
      }

      throw error;
    }
  }

  // ============ KPI METHODS ============

  async getKPIs(params?: Record<string, any>): Promise<PaginatedResponse<KPI>> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query ? `${API_ENDPOINTS.kpi.list}?${query}` : API_ENDPOINTS.kpi.list;
    return this.request("GET", endpoint);
  }

  async detectColumns(sourceId: number): Promise<AutoKPIDetectResponse> {
    return this.request("POST", API_ENDPOINTS.kpi.autoDetect, { source_id: sourceId });
  }

  async getKPI(id: string): Promise<KPI> {
    return this.request("GET", API_ENDPOINTS.kpi.detail(id));
  }

  async calculateKPI(id: string): Promise<KPICalculation> {
    return this.request("POST", API_ENDPOINTS.kpi.calculate(id));
  }

  async getKPIHistory(id: string, params?: { months?: number }): Promise<KPICalculation[]> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query
      ? `${API_ENDPOINTS.kpi.history(id)}?${query}`
      : API_ENDPOINTS.kpi.history(id);
    return this.request("GET", endpoint);
  }

  async detectAnomalies(id: string): Promise<KPIAnomaly> {
    return this.request("GET", API_ENDPOINTS.kpi.anomalies(id));
  }

  async getForecast(id: string, params?: { periods?: number }): Promise<KPIForecast> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query
      ? `${API_ENDPOINTS.kpi.forecast(id)}?${query}`
      : API_ENDPOINTS.kpi.forecast(id);
    return this.request("GET", endpoint);
  }

  async getVarianceAnalysis(id: string): Promise<any> {
    return this.request("GET", API_ENDPOINTS.kpi.variance(id));
  }

  // ============ CONFLICTS (M3) ============

  async getConflicts(params?: Record<string, any>): Promise<PaginatedResponse<any>> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query
      ? `${API_ENDPOINTS.conflicts.list}?${query}`
      : API_ENDPOINTS.conflicts.list;
    return this.request("GET", endpoint);
  }

  async getConflict(id: number): Promise<any> {
    return this.request("GET", `${API_ENDPOINTS.conflicts.list}${id}/`);
  }

  async resolveConflict(
    id: number,
    payload: {
      resolution_method: string;
      chosen_value?: any;
      resolution_notes?: string;
      requires_approval?: boolean;
    },
  ): Promise<any> {
    return this.request("POST", API_ENDPOINTS.conflicts.resolve(String(id)), payload);
  }

  async acknowledgeConflict(id: number): Promise<any> {
    return this.request("POST", `${API_ENDPOINTS.conflicts.list}${id}/acknowledge/`);
  }

  async detectConflicts(source_id: number, check_types?: string[]): Promise<any> {
    return this.request("POST", "/api/conflits/detect/", {
      source_id,
      check_types: check_types || [],
    });
  }

  async getConflictGuidance(id: number): Promise<any> {
    return this.request("GET", `${API_ENDPOINTS.conflicts.list}${id}/guidance/`);
  }

  async getConflictDashboardStats(): Promise<any> {
    return this.request("GET", `${API_ENDPOINTS.conflicts.list}dashboard_stats/`);
  }

  // ============ KPI ALERTS METHODS ============

  async getAlerts(params?: Record<string, any>): Promise<PaginatedResponse<KPIAlert>> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query ? `${API_ENDPOINTS.alerts.list}?${query}` : API_ENDPOINTS.alerts.list;
    return this.request("GET", endpoint);
  }

  async getAlert(id: string): Promise<KPIAlertDetail> {
    return this.request("GET", API_ENDPOINTS.alerts.detail(id));
  }

  async createAlert(data: KPIAlertPayload): Promise<KPIAlertPayload> {
    return this.request("POST", API_ENDPOINTS.alerts.create, data);
  }

  async updateAlert(id: string, data: KPIAlertPayload): Promise<KPIAlertPayload> {
    return this.request("PUT", API_ENDPOINTS.alerts.detail(id), data);
  }

  async patchAlert(id: string, data: Partial<KPIAlertPayload>): Promise<KPIAlertPayload> {
    return this.request("PATCH", API_ENDPOINTS.alerts.detail(id), data);
  }

  async deleteAlert(id: string): Promise<void> {
    return this.request("DELETE", API_ENDPOINTS.alerts.detail(id));
  }

  async acknowledgeAlert(
    id: string,
    notes?: string,
  ): Promise<{ status: string; acknowledged_by: string; acknowledged_at: string }> {
    return this.request("POST", API_ENDPOINTS.alerts.acknowledge(id), notes ? { notes } : {});
  }

  async getRecentAlerts(
    hours = 24,
  ): Promise<{ period_hours: number; count: number; alerts: KPIAlert[] }> {
    return this.request("GET", `${API_ENDPOINTS.alerts.recentlyTriggered}?hours=${hours}`);
  }

  // ============ DASHBOARD PREFERENCES METHODS ============

  async getPreferences(): Promise<UserPreference> {
    return this.request("GET", API_ENDPOINTS.dashboard.preferences);
  }

  async updatePreferences(data: Partial<UserPreference>): Promise<UserPreference> {
    return this.request("PUT", API_ENDPOINTS.dashboard.preferences, data);
  }

  async resetPreferences(): Promise<UserPreference> {
    return this.request("POST", API_ENDPOINTS.dashboard.preferencesReset);
  }

  // ============ SAVED VIEWS METHODS ============

  async getSavedViews(): Promise<SavedView[]> {
    const response = await this.request<PaginatedResponse<SavedView>>(
      "GET",
      API_ENDPOINTS.dashboard.views,
    );
    return response.results;
  }

  async getSavedView(id: string): Promise<SavedView> {
    return this.request("GET", API_ENDPOINTS.dashboard.viewDetail(id));
  }

  async createSavedView(data: Partial<SavedView>): Promise<SavedView> {
    return this.request("POST", API_ENDPOINTS.dashboard.views, data);
  }

  async updateSavedView(id: string, data: Partial<SavedView>): Promise<SavedView> {
    return this.request("PUT", API_ENDPOINTS.dashboard.viewDetail(id), data);
  }

  async deleteSavedView(id: string): Promise<void> {
    return this.request("DELETE", API_ENDPOINTS.dashboard.viewDetail(id));
  }

  async setDefaultView(id: string): Promise<SavedView> {
    return this.request("POST", API_ENDPOINTS.dashboard.viewDefault(id));
  }

  async duplicateView(id: string): Promise<SavedView> {
    return this.request("POST", API_ENDPOINTS.dashboard.viewDuplicate(id));
  }

  async loadDashboard(sourceId: number): Promise<any> {
    return this.request("GET", `${API_ENDPOINTS.dashboard.autoBuild}?source_id=${sourceId}`);
  }

  async autoBuildDashboard(
    sourceId: number,
    periodStart?: string,
    periodEnd?: string,
    filters?: Record<string, any>,
  ): Promise<any> {
    const body: Record<string, any> = { source_id: sourceId };
    if (periodStart) body.period_start = periodStart;
    if (periodEnd) body.period_end = periodEnd;
    if (filters) body.filters = filters;
    return this.request("POST", API_ENDPOINTS.dashboard.autoBuild, body);
  }

  async addWidgetToDashboard(sourceId: number, config: Record<string, any>): Promise<any> {
    return this.request("POST", API_ENDPOINTS.dashboard.addWidget, { source_id: sourceId, config });
  }

  async deleteWidget(widgetId: number): Promise<void> {
    return this.request("DELETE", `/api/dashboard/widgets/${widgetId}/`);
  }

  async updateWidgetChartType(widgetId: number, chartType: string): Promise<any> {
    return this.request("PATCH", `/api/dashboard/widgets/${widgetId}/chart_type/`, {
      chart_type: chartType,
    });
  }

  async reorderWidgets(
    items: {
      id: number;
      position_x: number;
      position_y: number;
      width?: number;
      height?: number;
    }[],
  ): Promise<any> {
    return this.request("POST", API_ENDPOINTS.dashboard.widgetReorder, { widgets: items });
  }

  async listWidgets(params?: Record<string, string>): Promise<any> {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request("GET", API_ENDPOINTS.dashboard.widgets + query);
  }

  // ============ WORKBENCH METHODS ============

  async getPivot(data: any): Promise<any> {
    return this.request("POST", API_ENDPOINTS.workbench.pivot, data);
  }

  async computeMetric(data: any): Promise<any> {
    return this.request("POST", API_ENDPOINTS.workbench.metric, data);
  }

  async getAvailableFilters(params?: Record<string, string>): Promise<any> {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request("GET", API_ENDPOINTS.workbench.filters + query);
  }

  async buildAdvancedPivot(config: any): Promise<any> {
    return this.request("POST", "/api/kpi/pivot/advanced/", config);
  }

  async drillDownPivot(payload: any): Promise<any> {
    return this.request("POST", "/api/kpi/pivot/drill-down/", payload);
  }

  async exportPivotToExcel(config: any): Promise<Blob> {
    const url = `/api/kpi/pivot/export/`;
    const fullUrl = `${this.baseUrl}${url}`;
    const headers: HeadersInit = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(fullUrl, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.error || "Export failed",
        data: errorData,
      };
    }
    return response.blob();
  }

  async exportPivotToPDF(config: any): Promise<Blob> {
    const url = `/api/kpi/pivot/export/pdf/`;
    const fullUrl = `${this.baseUrl}${url}`;
    const headers: HeadersInit = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(fullUrl, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.error || "PDF export failed",
        data: errorData,
      };
    }
    return response.blob();
  }

  async exportDashboardToPDF(sourceId: number): Promise<Blob> {
    const url = `${this.baseUrl}/api/dashboard/export/pdf/`;
    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ source_id: sourceId }),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.error || "Export PDF échoué",
        data: errorData,
      };
    }
    return response.blob();
  }

  // ============ DATA CLEANING (M2) METHODS ============

  async getCleaningSuggestions(sourceId: number): Promise<any> {
    return this.request<CleaningSuggestion>(
      "GET",
      `/api/nettoyage/sources/${sourceId}/suggestions/`,
    );
  }

  async previewCleaning(sourceId: number, payload: any): Promise<CleaningPreviewResponse> {
    return this.request<CleaningPreviewResponse>(
      "POST",
      `/api/nettoyage/sources/${sourceId}/preview/`,
      payload,
    );
  }

  async applyCleaning(sourceId: number, payload: any): Promise<any> {
    return this.request("POST", `/api/nettoyage/sources/${sourceId}/apply/`, payload);
  }

  async applyCleaningAsync(sourceId: number, payload: any): Promise<CleaningJobResponse> {
    return this.request<CleaningJobResponse>(
      "POST",
      `/api/nettoyage/sources/${sourceId}/apply-async/`,
      payload,
    );
  }

  async getCleaningJobs(
    params?: Record<string, any>,
  ): Promise<PaginatedResponse<CleaningJobResponse>> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query ? `/api/nettoyage/jobs/?${query}` : `/api/nettoyage/jobs/`;
    return this.request("GET", endpoint);
  }

  async getCleaningJob(jobId: number): Promise<CleaningJobResponse> {
    return this.request<CleaningJobResponse>("GET", `/api/nettoyage/jobs/${jobId}/`);
  }

  async getCleaningJobDetail(jobId: number): Promise<CleaningJobDetail> {
    return this.request<CleaningJobDetail>("GET", `/api/nettoyage/jobs/${jobId}/`);
  }

  async getCleaningComparison(jobId: number): Promise<CleaningComparison> {
    return this.request<CleaningComparison>("GET", `/api/nettoyage/jobs/${jobId}/comparison/`);
  }

  async validateCleaningJob(
    jobId: number,
    payload: { is_validated: boolean; validation_notes?: string },
  ): Promise<any> {
    return this.request("POST", `/api/nettoyage/jobs/${jobId}/validate/`, payload);
  }

  // ============ STRUCTURE DETECTION - PLAN REVIEW METHODS (M2) ============

  async structuralDetect(
    sourceId: number,
    payload: { sheet_name?: string; force_llm?: boolean; validation_config?: Record<string, any> },
  ): Promise<any> {
    return this.request(
      "POST",
      `/api/nettoyage/structure/sources/${sourceId}/structural-detect/`,
      payload,
    );
  }

  async previewPlanRules(
    sourceId: number,
    reconstructionPlan: Record<string, any>,
  ): Promise<{ rules: any[]; total_rules: number; plan_summary: Record<string, any> }> {
    return this.request("POST", `/api/nettoyage/structure/sources/${sourceId}/plan-preview/`, {
      reconstruction_plan: reconstructionPlan,
    });
  }

  async applyPlan(
    sourceId: number,
    reconstructionPlan: Record<string, any>,
    executeCleaning = false,
  ): Promise<any> {
    return this.request("POST", `/api/nettoyage/structure/sources/${sourceId}/apply-plan/`, {
      reconstruction_plan: reconstructionPlan,
      execute_cleaning: executeCleaning,
    });
  }

  async executeAfterReview(sourceId: number, pipelineId: number): Promise<any> {
    return this.request(
      "POST",
      `/api/nettoyage/structure/sources/${sourceId}/execute-after-review/`,
      { pipeline_id: pipelineId },
    );
  }

  async getStructuralRuns(sourceId?: number): Promise<any[]> {
    const params = sourceId ? `?source_id=${sourceId}` : "";
    return this.request<any[]>("GET", `/api/nettoyage/structure/structural-runs/${params}`);
  }

  async getStructuralRun(runId: number): Promise<any> {
    return this.request<any>("GET", `/api/nettoyage/structure/structural-runs/${runId}/`);
  }

  async validateStructuralRun(
    runId: number,
    payload: {
      correction_type?: string;
      description?: string;
      apply_plan?: boolean;
      execute_cleaning?: boolean;
    },
  ): Promise<any> {
    return this.request(
      "POST",
      `/api/nettoyage/structure/structural-runs/${runId}/validate/`,
      payload,
    );
  }

  // ============ DATA INGESTION (M1) METHODS ============

  async getImportTemplates(): Promise<ImportTemplate[]> {
    const res = await this.request<{ results?: ImportTemplate[] }>(
      "GET",
      "/api/ingestion/templates/",
    );
    return Array.isArray(res) ? res : res.results || [];
  }

  async listDataSources(params?: Record<string, any>): Promise<DataSourceDetail[]> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query ? `/api/ingestion/sources/?${query}` : `/api/ingestion/sources/`;
    const res = await this.request<{ results?: DataSourceDetail[] } | DataSourceDetail[]>(
      "GET",
      endpoint,
    );
    return Array.isArray(res) ? res : res.results || [];
  }

  async listIngestionJobs(params?: Record<string, any>): Promise<IngestionJob[]> {
    const query = params
      ? new URLSearchParams(
          Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
        ).toString()
      : "";
    const endpoint = query ? `/api/ingestion/jobs/?${query}` : `/api/ingestion/jobs/`;
    const res = await this.request<{ results?: IngestionJob[] } | IngestionJob[]>("GET", endpoint);
    return Array.isArray(res) ? res : res.results || [];
  }

  async getDataSource(sourceId: number): Promise<DataSourceDetail> {
    return this.request<DataSourceDetail>("GET", `/api/ingestion/sources/${sourceId}/`);
  }

  async getSourceRawData(sourceId: number, page = 1, pageSize = 10): Promise<any> {
    const endpoint = `/api/ingestion/sources/${sourceId}/raw-data/?page=${page}&page_size=${pageSize}`;
    return this.request<{ results?: any[] }>("GET", endpoint);
  }

  async getSourceRawDataBySheet(
    sourceId: number,
    sheetName: string,
    page = 1,
    pageSize = 10,
  ): Promise<any> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sheet_name: sheetName,
    });
    const endpoint = `/api/ingestion/sources/${sourceId}/raw-data/?${params.toString()}`;
    return this.request<{ results?: any[] }>("GET", endpoint);
  }

  async deleteSource(sourceId: number): Promise<void> {
    return this.request<void>("DELETE", `/api/ingestion/sources/${sourceId}/`);
  }

  async getIngestionJob(jobId: number): Promise<IngestionJob> {
    return this.request<IngestionJob>("GET", `/api/ingestion/jobs/${jobId}/`);
  }

  async previewImport(form: FormData): Promise<IngestionPreviewResponse> {
    const url = `${this.baseUrl}/api/ingestion/sources/preview/`;
    const headers: HeadersInit = {};
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const response = await fetch(url, { method: "POST", headers, body: form });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.detail || response.statusText,
        data: errorData,
      };
    }
    return response.json();
  }

  async uploadImportAsync(form: FormData): Promise<IngestionJob> {
    const url = `${this.baseUrl}/api/ingestion/sources/async-upload/`;
    const headers: HeadersInit = {};
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const response = await fetch(url, { method: "POST", headers, body: form });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw {
        status: response.status,
        message: errorData.detail || response.statusText,
        data: errorData,
      };
    }
    return response.json();
  }

  // Multi-sheet relations
  async getSheetRelations(sourceId: number): Promise<SheetRelation[]> {
    const res = await this.request<{ results?: SheetRelation[] } | SheetRelation[]>(
      "GET",
      `/api/ingestion/sources/${sourceId}/relations/`,
    );
    return Array.isArray(res) ? res : (res as any)?.results || [];
  }

  async createSheetRelation(
    sourceId: number,
    data: {
      relation_name: string;
      from_sheet: string;
      from_column: string;
      to_sheet: string;
      to_column: string;
      join_type?: string;
    },
  ): Promise<SheetRelation> {
    return this.request<SheetRelation>(
      "POST",
      `/api/ingestion/sources/${sourceId}/relations/create/`,
      data,
    );
  }

  async deleteSheetRelation(sourceId: number, relationId: number): Promise<void> {
    return this.request<void>(
      "DELETE",
      `/api/ingestion/sources/${sourceId}/relations/${relationId}/`,
    );
  }

  async suggestRelations(sourceId: number): Promise<{ suggestions: RelationSuggestion[] }> {
    return this.request<{ suggestions: RelationSuggestion[] }>(
      "GET",
      `/api/ingestion/sources/${sourceId}/suggest-relations/`,
    );
  }

  async getJoinedView(
    sourceId: number,
    options?: {
      sheet_names?: string[];
      relation_ids?: number[];
    },
  ): Promise<JoinedViewResponse> {
    return this.request<JoinedViewResponse>(
      "POST",
      `/api/ingestion/sources/${sourceId}/joined-view/`,
      options || {},
    );
  }

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    return this.request<{ message: string }>("POST", "/api/auth/password-reset/request/", {
      email,
    });
  }

  async confirmPasswordReset(payload: {
    uid: string;
    token: string;
    new_password: string;
    new_password_confirm: string;
  }): Promise<{ message: string }> {
    return this.request<{ message: string }>("POST", "/api/auth/password-reset/confirm/", payload);
  }

  // M6 — Interprétation IA
  async interpretKPIs(
    question: string,
    options?: {
      source_id?: number;
      widget_ids?: number[];
      kpi_ids?: number[];
      max_kpis?: number;
      persist?: boolean;
      model?: string;
    },
  ): Promise<AIInterpretationResponse> {
    return this.request<AIInterpretationResponse>("POST", getUrl(API_ENDPOINTS.ia.interpret), {
      question,
      source_id: options?.source_id,
      widget_ids: options?.widget_ids,
      kpi_ids: options?.kpi_ids,
      max_kpis: options?.max_kpis ?? 15,
      persist: options?.persist ?? true,
      model: options?.model,
    });
  }

  async getKPIsBySource(sourceId: number): Promise<SourceKPIsResponse> {
    return this.request<SourceKPIsResponse>("GET", getUrl(API_ENDPOINTS.ia.sourceKpis(sourceId)));
  }

  async getAIHistory(page = 1): Promise<AIHistoryResponse> {
    return this.request<AIHistoryResponse>(
      "GET",
      `${getUrl(API_ENDPOINTS.ia.history)}?page=${page}`,
    );
  }

  // M7 — Détection d'anomalies
  async listAnomalies(page = 1, severity?: string): Promise<AnomalyListResponse> {
    const params = new URLSearchParams({ page: String(page) });
    if (severity) params.set("severity", severity);
    return this.request<AnomalyListResponse>(
      "GET",
      `${getUrl(API_ENDPOINTS.anomalies.list)}?${params}`,
    );
  }

  async getAnomalyDetail(id: number): Promise<AnomalyDetail> {
    return this.request<AnomalyDetail>("GET", getUrl(API_ENDPOINTS.anomalies.detail(id)));
  }

  async updateAnomalyStatus(id: number, data: AnomalyStatusUpdate): Promise<AnomalyDetail> {
    return this.request<AnomalyDetail>("PATCH", getUrl(API_ENDPOINTS.anomalies.detail(id)), data);
  }

  async runIsolationForest(payload: IsolationForestRunRequest): Promise<IsolationForestResult> {
    return this.request<IsolationForestResult>(
      "POST",
      getUrl(API_ENDPOINTS.anomalies.runIsolationForest),
      payload,
    );
  }

  // M8 — Chatbot
  async listChatSessions(): Promise<ChatSession[]> {
    return this.request<ChatSession[]>("GET", getUrl(API_ENDPOINTS.chatbot.sessions));
  }

  async createChatSession(data?: {
    session_name?: string;
    bot_personality?: string;
  }): Promise<ChatSessionDetail> {
    return this.request<ChatSessionDetail>(
      "POST",
      getUrl(API_ENDPOINTS.chatbot.sessions),
      data || {},
    );
  }

  async getChatSession(id: number): Promise<ChatSessionDetail> {
    return this.request<ChatSessionDetail>("GET", getUrl(API_ENDPOINTS.chatbot.sessionDetail(id)));
  }

  async getChatMessages(sessionId: number): Promise<ChatMessage[]> {
    return this.request<ChatMessage[]>("GET", getUrl(API_ENDPOINTS.chatbot.messages(sessionId)));
  }

  async sendChatMessage(
    sessionId: number,
    content: string,
    options?: { persist_analysis?: boolean; model?: string; context?: Record<string, any> },
  ): Promise<{
    session: ChatSession;
    user_message: ChatMessage;
    bot_message: ChatMessage;
    analysis_id: number | null;
  }> {
    return this.request("POST", getUrl(API_ENDPOINTS.chatbot.messages(sessionId)), {
      content,
      persist_analysis: options?.persist_analysis ?? true,
      model: options?.model,
      context: options?.context,
    });
  }

  async deleteChatSession(id: number): Promise<void> {
    return this.request<void>("DELETE", getUrl(API_ENDPOINTS.chatbot.sessionDetail(id)));
  }

  // ─── Reporting ─────────────────────────────────────────────

  async listReportConfigs(): Promise<any[]> {
    const data = await this.request<any>("GET", getUrl(API_ENDPOINTS.reports.list));
    return Array.isArray(data) ? data : (data?.results ?? []);
  }

  async createReportConfig(data: any): Promise<any> {
    return this.request<any>("POST", getUrl(API_ENDPOINTS.reports.list), data);
  }

  async updateReportConfig(id: number, data: any): Promise<any> {
    return this.request<any>("PATCH", getUrl(API_ENDPOINTS.reports.detail(id)), data);
  }

  async deleteReportConfig(id: number): Promise<void> {
    return this.request<void>("DELETE", getUrl(API_ENDPOINTS.reports.detail(id)));
  }

  async triggerReport(configId: number): Promise<any> {
    return this.request<any>("POST", getUrl(API_ENDPOINTS.reports.trigger), {
      config_id: configId,
    });
  }

  async getReportHistory(): Promise<any[]> {
    const data = await this.request<any>("GET", getUrl(API_ENDPOINTS.reports.history));
    return Array.isArray(data) ? data : (data?.results ?? []);
  }

  // ─── Activity & Presence ──────────────────────────────

  async getActivityFeed(limit = 50): Promise<any[]> {
    const data = await this.request<any>(
      "GET",
      `${getUrl(API_ENDPOINTS.activity.feed)}?limit=${limit}`,
    );
    return data?.activities ?? [];
  }

  async sendPresenceHeartbeat(page = ""): Promise<void> {
    await this.request<any>("POST", getUrl(API_ENDPOINTS.presence.heartbeat), { page });
  }

  async getOnlineUsers(): Promise<any[]> {
    const data = await this.request<any>("GET", getUrl(API_ENDPOINTS.presence.list));
    return data?.online_users ?? [];
  }
}

// Instance globale du client
export const apiClient = new ApiClient();

// Utilitaire pour gérer les erreurs API
export function handleApiError(error: any, defaultMessage = "Une erreur est survenue"): string {
  console.error("API Error:", error);

  const extractValidationMessage = (data: any): string | null => {
    if (!data || typeof data !== "object") return null;

    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
    if (typeof data.error === "string") return data.error;

    const firstField = Object.values(data).find((value) => {
      if (typeof value === "string") return value;
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === "string") return value[0];
      return null;
    });

    if (typeof firstField === "string") return firstField;
    if (Array.isArray(firstField) && typeof firstField[0] === "string") return firstField[0];

    return null;
  };

  const validationMessage = extractValidationMessage(error.data);
  if (validationMessage) {
    return validationMessage;
  }

  if (error.status === 401) {
    return "Session expirée, veuillez vous reconnecter.";
  }

  if (error.status === 403) {
    return "Vous n'avez pas les permissions pour cette action.";
  }

  if (error.status === 404) {
    return "La ressource n'a pas été trouvée.";
  }

  if (error.status === 400 && error.data?.detail) {
    return error.data.detail;
  }

  if (typeof error.message === "string") {
    return error.message;
  }

  return defaultMessage;
}
