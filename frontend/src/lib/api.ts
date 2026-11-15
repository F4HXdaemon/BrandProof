import {
  User,
  DashboardData,
  Fact,
  Guideline,
  Term,
  Rule,
  Document,
  DocumentChunk,
  Review,
  ReviewDetail,
  Claim,
  Finding,
  Approval,
  AuditEvent,
  Organization,
  CsvImportResult,
  ApplicableKnowledgeResponse,
  Comment,
  DiffResult,
  InsightsData,
  EvaluationResult,
  RegisterPayload,
  AuthResponse,
} from "./types";

export function getApiBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  const isProduction = process.env.NODE_ENV === "production";

  let url = envUrl ? envUrl.trim().replace(/\/+$/, "") : "http://localhost:8000/api/v1";

  if (isProduction && typeof window !== "undefined") {
    if (!envUrl) {
      throw new Error("Configuration Error: NEXT_PUBLIC_API_URL is required in production environment.");
    }
    if (!url.startsWith("https://")) {
      throw new Error(`Security Error: Production NEXT_PUBLIC_API_URL must use HTTPS protocol. Received: ${url}`);
    }
    if (url.includes("localhost") || url.includes("127.0.0.1")) {
      throw new Error(`Security Error: Production NEXT_PUBLIC_API_URL cannot target localhost or 127.0.0.1.`);
    }
  }

  // Ensure trailing /api/v1 is present
  if (!url.endsWith("/api/v1")) {
    url = `${url}/api/v1`;
  }

  return url;
}

export const API_BASE = getApiBase();

class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("brandproof_token");
}

export function setToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("brandproof_token", token);
  }
}

export function removeToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("brandproof_token");
  }
}

async function downloadBlob(endpoint: string, fallbackFilename: string = "download"): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${getApiBase()}${cleanEndpoint}`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    let err = `Download failed with status ${response.status}`;
    try {
      const j = await response.json();
      err = j.detail || err;
    } catch {}
    throw new ApiError(response.status, err);
  }
  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  const disposition = response.headers.get("content-disposition");
  let filename = fallbackFilename;
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/);
    if (match && match[1]) filename = match[1];
  }
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(blobUrl);
  document.body.removeChild(a);
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${getApiBase()}${cleanEndpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      0,
      "Unable to reach BrandProof backend. If the backend is waking up on Render Free tier, it may take ~45s. Please retry in a few moments.",
      err
    );
  }

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred";
    let errorData = null;
    try {
      const errorJson = await response.json();
      if (Array.isArray(errorJson.detail)) {
        errorDetail = errorJson.detail
          .map((d: any) => d.msg || (typeof d === "string" ? d : JSON.stringify(d)))
          .join(". ");
      } else {
        errorDetail = errorJson.detail || errorJson.message || errorDetail;
      }
      errorData = errorJson;
    } catch {
      errorDetail = await response.text();
    }
    throw new ApiError(response.status, errorDetail, errorData);
  }

  // If response has no content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Authentication
  auth: {
    login: async (email: string, password: string) =>
      request<AuthResponse>(
        "/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }
      ),
    register: async (payload: RegisterPayload) =>
      request<AuthResponse>(
        "/auth/register",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      ),
    getMe: async () => request<User>("/auth/me"),
  },

  // Organizations
  organizations: {
    getCurrent: async () => request<Organization>("/organizations/current"),
    getMembers: async () => request<User[]>("/organizations/current/members"),
  },

  // Dashboard
  dashboard: {
    getMetrics: async () => request<DashboardData>("/dashboard"),
  },

  // Facts
  facts: {
    list: async (params?: {
      q?: string;
      status?: string;
      product_scope?: string;
      region_scope?: string;
      channel_scope?: string;
      owner_id?: string;
      expiring_soon?: boolean;
      is_expired?: boolean;
    }) => {
      const query = new URLSearchParams();
      if (params?.q) query.append("q", params.q);
      if (params?.status) query.append("status", params.status);
      if (params?.product_scope) query.append("product_scope", params.product_scope);
      if (params?.region_scope) query.append("region_scope", params.region_scope);
      if (params?.channel_scope) query.append("channel_scope", params.channel_scope);
      if (params?.owner_id) query.append("owner_id", params.owner_id);
      if (params?.expiring_soon) query.append("expiring_soon", "true");
      if (params?.is_expired) query.append("is_expired", "true");
      return request<Fact[]>(`/facts?${query.toString()}`);
    },
    get: async (id: string) => request<Fact>(`/facts/${id}`),
    create: async (data: Partial<Fact>) =>
      request<Fact>("/facts", { method: "POST", body: JSON.stringify(data) }),
    update: async (id: string, data: Partial<Fact>) =>
      request<Fact>(`/facts/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    archive: async (id: string) =>
      request<Fact>(`/facts/${id}/archive`, { method: "PUT" }),
    delete: async (id: string) =>
      request<{ message: string }>(`/facts/${id}`, { method: "DELETE" }),
    importCsv: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<CsvImportResult>("/facts/import-csv", {
        method: "POST",
        body: formData,
      });
    },
  },

  // Guidelines
  guidelines: {
    list: async (params?: {
      category?: string;
      severity?: string;
      product_scope?: string;
      region_scope?: string;
      channel_scope?: string;
      status?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.category) query.append("category", params.category);
      if (params?.severity) query.append("severity", params.severity);
      if (params?.product_scope) query.append("product_scope", params.product_scope);
      if (params?.region_scope) query.append("region_scope", params.region_scope);
      if (params?.channel_scope) query.append("channel_scope", params.channel_scope);
      if (params?.status) query.append("status", params.status);
      return request<Guideline[]>(`/guidelines?${query.toString()}`);
    },
    get: async (id: string) => request<Guideline>(`/guidelines/${id}`),
    create: async (data: Partial<Guideline>) =>
      request<Guideline>("/guidelines", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: async (id: string, data: Partial<Guideline>) =>
      request<Guideline>(`/guidelines/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    archive: async (id: string) =>
      request<Guideline>(`/guidelines/${id}/archive`, { method: "PUT" }),
    delete: async (id: string) =>
      request<{ message: string }>(`/guidelines/${id}`, { method: "DELETE" }),
  },

  // Terminology
  terms: {
    list: async (params?: {
      q?: string;
      status?: string;
      product_scope?: string;
      region_scope?: string;
      channel_scope?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.q) query.append("q", params.q);
      if (params?.status) query.append("status", params.status);
      if (params?.product_scope) query.append("product_scope", params.product_scope);
      if (params?.region_scope) query.append("region_scope", params.region_scope);
      if (params?.channel_scope) query.append("channel_scope", params.channel_scope);
      return request<Term[]>(`/terms?${query.toString()}`);
    },
    get: async (id: string) => request<Term>(`/terms/${id}`),
    create: async (data: Partial<Term>) =>
      request<Term>("/terms", { method: "POST", body: JSON.stringify(data) }),
    update: async (id: string, data: Partial<Term>) =>
      request<Term>(`/terms/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    archive: async (id: string) =>
      request<Term>(`/terms/${id}/archive`, { method: "PUT" }),
    delete: async (id: string) =>
      request<{ message: string }>(`/terms/${id}`, { method: "DELETE" }),
    importCsv: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<CsvImportResult>("/terms/import-csv", {
        method: "POST",
        body: formData,
      });
    },
  },

  // Rules
  rules: {
    list: async (params?: {
      rule_type?: string;
      severity?: string;
      product_scope?: string;
      region_scope?: string;
      channel_scope?: string;
      status?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.rule_type) query.append("rule_type", params.rule_type);
      if (params?.severity) query.append("severity", params.severity);
      if (params?.product_scope) query.append("product_scope", params.product_scope);
      if (params?.region_scope) query.append("region_scope", params.region_scope);
      if (params?.channel_scope) query.append("channel_scope", params.channel_scope);
      if (params?.status) query.append("status", params.status);
      return request<Rule[]>(`/rules?${query.toString()}`);
    },
    get: async (id: string) => request<Rule>(`/rules/${id}`),
    create: async (data: Partial<Rule>) =>
      request<Rule>("/rules", { method: "POST", body: JSON.stringify(data) }),
    update: async (id: string, data: Partial<Rule>) =>
      request<Rule>(`/rules/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    archive: async (id: string) =>
      request<Rule>(`/rules/${id}/archive`, { method: "PUT" }),
    delete: async (id: string) =>
      request<{ message: string }>(`/rules/${id}`, { method: "DELETE" }),
  },

  // Scoping Engine / Applicable Knowledge
  knowledge: {
    getApplicable: async (params?: {
      product?: string;
      region?: string;
      channel?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.product) query.append("product", params.product);
      if (params?.region) query.append("region", params.region);
      if (params?.channel) query.append("channel", params.channel);
      return request<ApplicableKnowledgeResponse>(`/knowledge/applicable?${query.toString()}`);
    },
  },

  // Documents
  documents: {
    list: async (params?: { status?: string; product?: string }) => {
      const query = new URLSearchParams();
      if (params?.status) query.append("status", params.status);
      if (params?.product) query.append("product", params.product);
      return request<Document[]>(`/documents?${query.toString()}`);
    },
    get: async (id: string) => request<Document>(`/documents/${id}`),
    upload: async (formData: FormData) =>
      request<Document>("/documents/upload", {
        method: "POST",
        body: formData,
      }),
    getChunks: async (documentId: string, versionId?: string) => {
      const url = versionId
        ? `/documents/${documentId}/chunks?version_id=${versionId}`
        : `/documents/${documentId}/chunks`;
      return request<DocumentChunk[]>(url);
    },
    download: async (documentId: string, filename?: string) =>
      downloadBlob(`/documents/${documentId}/download`, filename || "document"),
    delete: async (documentId: string) =>
      request<{ status: string; message: string }>(`/documents/${documentId}`, {
        method: "DELETE",
      }),
  },

  // Reviews
  reviews: {
    list: async (params?: {
      status?: string;
      product?: string;
      region?: string;
      channel?: string;
      creator_id?: string;
      document_id?: string;
      q?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.status) query.append("status", params.status);
      if (params?.product) query.append("product", params.product);
      if (params?.region) query.append("region", params.region);
      if (params?.channel) query.append("channel", params.channel);
      if (params?.creator_id) query.append("creator_id", params.creator_id);
      if (params?.document_id) query.append("document_id", params.document_id);
      if (params?.q) query.append("q", params.q);
      return request<Review[]>(`/reviews?${query.toString()}`);
    },
    get: async (id: string) => request<ReviewDetail>(`/reviews/${id}`),
    submitNew: async (formData: FormData) =>
      request<ReviewDetail>("/reviews/new", {
        method: "POST",
        body: formData,
      }),
    create: async (data: { document_id: string; summary?: string }) =>
      request<ReviewDetail>("/reviews", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateStatus: async (id: string, status: string) =>
      request<Review>(`/reviews/${id}/status?status=${status}`, {
        method: "PUT",
      }),
    acceptFix: async (reviewId: string, findingId: string, replacementText?: string) =>
      request<ReviewDetail>(`/reviews/${reviewId}/accept-fix`, {
        method: "POST",
        body: JSON.stringify({ finding_id: findingId, replacement_text: replacementText }),
      }),
    dismissFinding: async (reviewId: string, findingId: string, dismissalReason: string) =>
      request<ReviewDetail>(`/reviews/${reviewId}/dismiss-finding`, {
        method: "POST",
        body: JSON.stringify({ finding_id: findingId, dismissal_reason: dismissalReason }),
      }),
    getDiff: async (reviewId: string, baseVersionId?: string) => {
      const url = baseVersionId
        ? `/reviews/${reviewId}/diff?base_version_id=${baseVersionId}`
        : `/reviews/${reviewId}/diff`;
      return request<DiffResult>(url);
    },
    getComments: async (reviewId: string) =>
      request<Comment[]>(`/reviews/${reviewId}/comments`),
    addComment: async (reviewId: string, text: string, findingId?: string) =>
      request<Comment>(`/reviews/${reviewId}/comments`, {
        method: "POST",
        body: JSON.stringify({ text, finding_id: findingId }),
      }),
  },

  // Claims & Findings
  claims: {
    listForReview: async (reviewId: string) =>
      request<Claim[]>(`/claims/review/${reviewId}`),
  },
  findings: {
    listForReview: async (reviewId: string) =>
      request<Finding[]>(`/findings/review/${reviewId}`),
    create: async (data: Partial<Finding>) =>
      request<Finding>("/findings", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateStatus: async (id: string, status: string) =>
      request<Finding>(`/findings/${id}/status?status=${status}`, {
        method: "PUT",
      }),
  },

  // Approvals (Human decision point)
  approvals: {
    recordDecision: async (
      reviewId: string,
      data: {
        status: string;
        comments?: string;
        is_override?: boolean;
        override_reason?: string;
      }
    ) =>
      request<Approval>(`/approvals/review/${reviewId}`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  // Audit
  audit: {
    list: async (params?: {
      action?: string;
      entity_type?: string;
      limit?: number;
      offset?: number;
    }) => {
      const query = new URLSearchParams();
      if (params?.action) query.append("action", params.action);
      if (params?.entity_type) query.append("entity_type", params.entity_type);
      if (params?.limit) query.append("limit", params.limit.toString());
      if (params?.offset) query.append("offset", params.offset.toString());
      return request<AuditEvent[]>(`/audit?${query.toString()}`);
    },
  },

  // Live Insights
  insights: {
    get: async () => request<InsightsData>("/insights"),
  },

  // Evaluation Benchmarks
  evaluation: {
    run: async () => request<EvaluationResult>("/evaluation/run"),
    downloadCsv: async () =>
      downloadBlob("/evaluation/export", "brandproof_evaluation_results.csv"),
  },

  // Demo Switcher / Reset
  demo: {
    reset: async () =>
      request<{ status: string; message: string; personas: any[] }>("/demo/reset", {
        method: "POST",
      }),
  },
};

