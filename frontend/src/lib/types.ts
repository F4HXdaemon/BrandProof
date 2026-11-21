export type UserRole =
  | "Creator"
  | "Reviewer"
  | "Brand Manager"
  | "Fact Owner"
  | "Admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  title?: string;
  avatar_url?: string;
  is_active: boolean;
  organization_id: string;
  created_at: string;
}

export interface RegisterPayload {
  organization_name?: string;
  organization_slug?: string;
  email: string;
  password: string;
  full_name: string;
  invite_token?: string;
  role?: UserRole;
}

export interface InviteInfo {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  email?: string;
  valid: boolean;
}

export interface InviteResponse {
  invite_token: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  email?: string;
  expires_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  domain?: string;
  is_active: boolean;
  created_at: string;
}

export type FactStatus =
  | "Approved"
  | "Draft"
  | "Expired"
  | "Archived"
  | "Active"
  | "Expiring"
  | "Deprecated"
  | "In Review";

export type SeverityLevel =
  | "Blocker"
  | "High"
  | "Warning"
  | "Info"
  | "Critical"
  | "Medium"
  | "Low"
  | "Advisory";

export type RuleType =
  | "TERM_CHECK"
  | "REQUIRED_DISCLAIMER"
  | "FORBIDDEN_PHRASE"
  | "EXACT_VALUE"
  | "EXPIRY_CHECK"
  | "REGEX"
  | "ACCESSIBILITY"
  | "CUSTOM";

export interface Fact {
  id: string;
  organization_id: string;
  owner_id?: string;
  owner_name?: string;
  title: string;
  canonical_value: string;
  description?: string;
  source_reference: string;
  product_scope: string;
  region_scope: string;
  channel_scope: string;
  valid_from?: string;
  expires_at?: string;
  status: FactStatus;
  is_expired?: boolean;
  effective_status?: string;
  days_until_expiry?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Guideline {
  id: string;
  organization_id: string;
  title: string;
  description: string;
  category: string;
  severity: SeverityLevel;
  product_scope: string;
  region_scope: string;
  channel_scope: string;
  source_reference?: string;
  status?: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Term {
  id: string;
  organization_id: string;
  approved_term: string;
  term?: string;
  disallowed_variants: string[];
  replacement?: string;
  notes?: string;
  product_scope?: string;
  region_scope?: string;
  channel_scope?: string;
  status?: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Rule {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  rule_type: RuleType | string;
  severity: SeverityLevel;
  configuration: Record<string, any>;
  config?: Record<string, any>;
  source_reference?: string;
  product_scope?: string;
  region_scope?: string;
  channel_scope?: string;
  status?: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CsvImportResult {
  imported_count: number;
  total_attempted: number;
  errors: string[];
  failed_count: number;
  imported_items: any[];
}

export interface ApplicableKnowledgeResponse {
  scopes: { product: string; region: string; channel: string };
  counts: { facts: number; guidelines: number; terms: number; rules: number };
  facts: Fact[];
  guidelines: Guideline[];
  terms: Term[];
  rules: Rule[];
  expired_facts_excluded: Fact[];
}

export type DocumentStatus =
  | "Draft"
  | "Processing"
  | "Needs Review"
  | "Changes Requested"
  | "Approved"
  | "Rejected";

export interface DocumentChunk {
  id: string;
  document_version_id: string;
  sequence: number;
  chunk_type: "heading" | "paragraph" | "table" | "list_item" | string;
  text: string;
  page_number?: number | null;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  file_path: string;
  file_size: number;
  extracted_text?: string;
  error_message?: string;
  created_by_id?: string;
  chunks?: DocumentChunk[];
  created_at: string;
  updated_at?: string;
}

export interface Document {
  id: string;
  organization_id: string;
  creator_id?: string;
  creator_name?: string;
  title: string;
  filename: string;
  file_type: string;
  file_path: string;
  file_size: number;
  product: string;
  region: string;
  channel: string;
  status: DocumentStatus;
  processing_status?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  versions?: DocumentVersion[];
}

export type ReviewStatus =
  | "Pending"
  | "In Progress"
  | "Needs Review"
  | "Changes Requested"
  | "Approved"
  | "Rejected";

export type ClaimStatus =
  | "Proposed"
  | "Verified"
  | "Unverified"
  | "Disputed"
  | "SUPPORTED"
  | "CONFLICTS"
  | "EXPIRED"
  | "OUT_OF_SCOPE"
  | "UNSUPPORTED";

export type FindingStatus = "Open" | "Resolved" | "Waived" | "Dismissed" | "Fixed";

export interface Claim {
  id: string;
  review_id: string;
  document_id: string;
  text: string;
  claim_text?: string;
  claim_type?: string;
  location_metadata?: Record<string, any>;
  page_number?: number;
  paragraph_number?: number;
  confidence: number;
  status: ClaimStatus;
  matched_fact_id?: string;
  reasoning?: string;
  created_at: string;
}

export interface Finding {
  id: string;
  review_id: string;
  claim_id?: string;
  claim_text?: string;
  rule_id?: string;
  guideline_id?: string;
  fact_id?: string;
  finding_type?: string;
  severity: SeverityLevel;
  title?: string;
  message: string;
  suggestion?: string;
  suggested_replacement?: string;
  quoted_text?: string;
  start_offset?: number;
  end_offset?: number;
  page_number?: number;
  source_type?: string;
  source_id?: string;
  source_reference: string; // Critical rule: NO VALID SOURCE = NO FINDING
  checker?: string;
  confidence?: number;
  dismissal_reason?: string;
  status: FindingStatus;
  created_at: string;
}

export interface Approval {
  id: string;
  review_id: string;
  document_id: string;
  approver_id?: string;
  approver_name?: string;
  status: "Approved" | "Rejected" | "Changes Requested";
  comments?: string;
  is_override?: boolean;
  override_reason?: string;
  override_finding_ids?: string[];
  decided_at: string;
}

export interface Comment {
  id: string;
  organization_id: string;
  review_id: string;
  finding_id?: string;
  author_id?: string;
  author_name?: string;
  text: string;
  resolved: boolean;
  created_at: string;
}

export interface DiffToken {
  type: "unchanged" | "added" | "removed";
  value: string;
}

export interface DiffResult {
  review_id: string;
  base_version: { id: string; version_number: number; change_reason?: string };
  current_version: { id: string; version_number: number; change_reason?: string };
  stats: { words_added: number; words_removed: number; words_unchanged: number; total_changes: number };
  tokens: DiffToken[];
}

export interface InsightsData {
  metrics: {
    total_reviews: number;
    total_findings: number;
    open_blockers: number;
    resolved_findings: number;
    resolution_rate_percent: number;
    average_risk_score: number;
  };
  severity_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  risk_distribution: Record<string, number>;
  top_violated_rules: Array<{ name: string; count: number }>;
  top_violated_terms: Array<{ term: string; count: number }>;
  channel_distribution: Record<string, number>;
  product_distribution: Record<string, number>;
  claims_breakdown: Record<string, number>;
}

export interface EvaluationCase {
  case_id: string;
  title: string;
  text: string;
  expected_count: number;
  detected_count: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  missed_expected: Array<Record<string, any>>;
  detected_findings: Array<{
    title: string;
    type: string;
    severity: string;
    quoted?: string;
    source?: string;
  }>;
}

export interface EvaluationResult {
  metrics: {
    total_benchmark_cases: number;
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    precision: number;
    recall: number;
    f1_score: number;
    accuracy_percent: number;
  };
  cases: EvaluationCase[];
}

export interface Review {
  id: string;
  organization_id: string;
  document_id: string;
  version_id?: string;
  reviewer_id?: string;
  reviewer_name?: string;
  creator_name?: string;
  title?: string;
  document_title?: string;
  document_status?: DocumentStatus;
  status: ReviewStatus;
  summary?: string;
  product?: string;
  region?: string;
  channel?: string;
  content_type?: string;
  intended_audience?: string;
  purpose?: string;
  intent_card?: Record<string, any>;
  risk_score?: number;
  risk_level?: string;
  processing_status?: string;
  error_message?: string;
  claims_count: number;
  findings_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewDetail extends Review {
  document?: Document;
  version?: DocumentVersion;
  claims: Claim[];
  findings: Finding[];
  approvals: Approval[];
  comments?: Comment[];
  evidence_documents?: Evidence[];
}

export type EvidenceStatus =
  | "Uploaded"
  | "Processing"
  | "Validated"
  | "Invalid"
  | "Expired"
  | "Rejected"
  | "Unavailable";

export interface Evidence {
  id: string;
  organization_id: string;
  uploaded_by_id?: string;
  uploader_name?: string;
  uploaded_by_name?: string;
  title: string;
  filename: string;
  file_type: string;
  mime_type?: string;
  file_extension: string;
  file_size: number;
  file_hash?: string;
  status: EvidenceStatus;
  validation_errors?: string;
  description?: string;
  source_reference?: string;
  product_scope: string;
  region_scope: string;
  channel_scope: string;
  valid_from?: string;
  expires_at?: string;
  is_expired?: boolean;
  sha256_checksum?: string;
  associated_review_ids?: string[];
  associated_reviews_count: number;
  associated_claims_count: number;
  created_at: string;
  updated_at: string;
}

export interface EvidenceDetail extends Evidence {
  extracted_text?: string;
  associated_reviews: Array<{
    review_id: string;
    title: string;
    status: string;
    risk_score: number;
    relevance_notes?: string;
    associated_at?: string;
  }>;
  supported_claims: Array<{
    claim_id: string;
    review_id: string;
    claim_text: string;
    claim_type?: string;
    status: string;
    confidence: number;
  }>;
}

export interface AuditEvent {
  id: string;
  organization_id: string;
  actor_id?: string;
  actor_name?: string;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, any>;
  timestamp: string;
}

export interface SummaryCards {
  open_reviews: number;
  blocked_content: number;
  approved_this_week: number;
  active_facts: number;
  expiring_facts: number;
  findings_this_month: number;
}

export interface RiskOverview {
  overall_score: number;
  status: string;
  findings_by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    advisory: number;
  };
  unverified_claims_rate: number;
}

export interface DashboardData {
  metrics: SummaryCards;
  risk_overview: RiskOverview;
  recent_reviews: Review[];
  recent_activity: AuditEvent[];
}
