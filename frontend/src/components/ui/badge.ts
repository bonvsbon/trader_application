// ทางรอด — badge state -> semantic class. Mirrors the redesign mapping.
const ALLOW_SET = new Set([
  "ALLOW", "HEALTHY", "DEMO", "FILLED", "APPROVED", "OK", "MATCH", "AVAILABLE", "RUNNING",
]);
const WARN_SET = new Set([
  "WARN", "PENDING_APPROVAL", "PENDING", "SUBMITTED", "RECONCILIATION_REQUIRED", "NEAR", "RECONNECTING", "DRAFT",
]);
const BLOCK_SET = new Set([
  "BLOCK", "UNHEALTHY", "UNKNOWN", "REAL", "RISK_BLOCKED", "ERROR", "REJECTED",
  "CANCELLED", "MISMATCH", "NO PROVIDER", "ABNORMAL",
]);

export type BadgeTone = "allow" | "warn" | "block" | "accent" | "neutral" | "";

export function badgeClass(value: unknown): BadgeTone {
  const k = String(value ?? "").toUpperCase();
  if (ALLOW_SET.has(k)) return "allow";
  if (WARN_SET.has(k)) return "warn";
  if (BLOCK_SET.has(k)) return "block";
  return "";
}
