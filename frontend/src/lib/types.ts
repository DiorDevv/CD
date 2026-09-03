export type Role = "super_admin" | "soc_admin" | "dlp_admin" | "viewer";

export interface User {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  failed_attempts: number;
  locked_until: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  must_change_password: boolean;
  user: User;
}

export interface UserCreatedResponse {
  user: User;
  temporary_password: string;
}

export interface UserPage {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Dinamik jadvallar
// ---------------------------------------------------------------------------

export type TableSection = "soc" | "dlp" | "shared";

export type ColumnType =
  | "text"
  | "long_text"
  | "number"
  | "boolean"
  | "date"
  | "datetime"
  | "select"
  | "multi_select"
  | "user";

export interface SelectOption {
  value: string;
  label: string;
  color?: string;
}

export interface ColumnConfig {
  required?: boolean;
  default?: unknown;
  options?: SelectOption[];
  min?: number;
  max?: number;
}

export interface DynamicColumn {
  id: string;
  key: string;
  label: string;
  type: ColumnType;
  config: ColumnConfig;
  position: number;
}

export interface DynamicTable {
  id: string;
  section: TableSection;
  name: string;
  slug: string;
  description: string | null;
  position: number;
  is_archived: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  column_count: number;
  row_count: number;
}

export interface DynamicTableDetail extends DynamicTable {
  columns: DynamicColumn[];
}

export interface TablePage {
  items: DynamicTable[];
  total: number;
  limit: number;
  offset: number;
}

export interface DynamicRow {
  id: string;
  data: Record<string, unknown>;
  position: number | null;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RowPage {
  items: DynamicRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface RowRevision {
  id: string;
  row_id: string;
  action: "create" | "update" | "delete";
  data: Record<string, unknown> | null;
  changed_by: string | null;
  changed_at: string;
}

export interface DirectoryUser {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
}

// --- Eksport / yuklab olish ------------------------------------------------

export type ExportFormat = "csv" | "json" | "xlsx";

export type ExportJobStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export interface ExportJob {
  id: string;
  table_id: string;
  status: ExportJobStatus;
  format: ExportFormat;
  filters: { q?: string | null; sort?: string | null };
  file_name: string | null;
  row_count: number | null;
  file_size_bytes: number | null;
  checksum_sha256: string | null;
  error_message: string | null;
  has_share_link: boolean;
  share_expires_at: string | null;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
  downloaded_at: string | null;
  download_count: number;
}

export interface ShareLink {
  job_id: string;
  token: string;
  url: string;
  expires_at: string;
}

export const SECTION_LABELS: Record<TableSection, string> = {
  soc: "SOC",
  dlp: "DLP",
  shared: "Umumiy",
};

/** Rol asosida yozish mumkin bo'lgan bo'limlar (backend bilan bir xil qoida). */
export function writableSectionsFor(role: Role): TableSection[] {
  if (role === "super_admin") return ["soc", "dlp", "shared"];
  if (role === "soc_admin") return ["soc", "shared"];
  if (role === "dlp_admin") return ["dlp", "shared"];
  return [];
}

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: "Super Admin",
  soc_admin: "SOC Admin",
  dlp_admin: "DLP Admin",
  viewer: "Kuzatuvchi",
};

/** Role -> asosiy dashboard yo'nalishi */
export const ROLE_HOME: Record<Role, string> = {
  super_admin: "/super-admin/dashboard",
  soc_admin: "/soc/dashboard",
  dlp_admin: "/dlp/dashboard",
  viewer: "/viewer/dashboard",
};

/** data-role atributi uchun (aksent rang) */
export function roleAccent(role: Role): string {
  if (role === "soc_admin") return "soc";
  if (role === "dlp_admin") return "dlp";
  if (role === "viewer") return "viewer";
  return "super_admin";
}
