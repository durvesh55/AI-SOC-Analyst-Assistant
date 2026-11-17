export function fmtDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function fmtDay(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function userLabel(u) {
  if (!u) return "Unassigned";
  return u.full_name ? `${u.full_name} (${u.username})` : u.username;
}

export function pages(total, pageSize) {
  return Math.max(1, Math.ceil(total / pageSize));
}

const ACTION_LABELS = {
  LOGIN: "Logged in", LOGIN_FAILED: "Failed login", LOGOUT: "Logged out", REGISTER: "Registered",
  ALERT_CREATED: "Created alert", ALERT_UPDATED: "Updated alert", ALERT_STATUS_CHANGED: "Changed alert status",
  ALERT_ASSIGNED: "Assigned alert", CASE_CREATED: "Created case", CASE_UPDATED: "Updated case",
  CASE_ASSIGNED: "Assigned case", CASE_STATUS_CHANGED: "Changed case status", NOTE_ADDED: "Added note",
  CASE_CLOSED: "Closed case", CASE_REOPENED: "Reopened case", REPORT_GENERATED: "Generated report",
  USER_CREATED: "Created user", USER_UPDATED: "Updated user", PASSWORD_CHANGED: "Changed password",
  PROFILE_UPDATED: "Updated profile",
};
export const actionLabel = (a) => ACTION_LABELS[a] || a;
