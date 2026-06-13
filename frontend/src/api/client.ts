import axios from "axios";

// Relative baseURL: the Vite dev server proxies /api and /ws to the backend.
const apiToken = import.meta.env.VITE_API_TOKEN as string | undefined;
// The live MT5 EA bridge services its socket on a timer, so a risk preview is
// several seconds of serialized RPCs. Allow generous headroom over the mock
// bridge's instant responses; override with VITE_API_TIMEOUT_MS if needed.
const configuredTimeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 30000);
const apiTimeoutMs =
  Number.isFinite(configuredTimeoutMs) && configuredTimeoutMs > 0
    ? configuredTimeoutMs
    : 10000;
const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "",
  timeout: apiTimeoutMs,
  withCredentials: true,
  headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
});
let csrfToken: string | null = null;

http.interceptors.request.use((config) => {
  if (
    csrfToken &&
    ["post", "put", "patch", "delete"].includes(
      (config.method ?? "get").toLowerCase(),
    )
  ) {
    config.headers.set("X-CSRF-Token", csrfToken);
  }
  return config;
});

export function setCsrfToken(value: string | null) {
  csrfToken = value;
}

export interface AuthUser {
  id: number;
  mt5_login: number;
  display_name: string;
  role: string;
  mt5_account: {
    id: number;
    login: number;
    server: string;
    account_type: "DEMO" | "REAL";
  };
}

export interface AuthStatus {
  enabled: boolean;
  bootstrap_required: boolean;
  authenticated: boolean;
  csrf_token?: string | null;
  user: AuthUser | null;
}

export interface OrderResult {
  idempotency_key: string;
  state: string;
  decision: string;
  reasons: string[];
  warnings: string[];
  order_id: number | null;
  account_type: string;
  trading_mode: string;
  message: string;
}

export interface OrderTicket {
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  sl?: number | null;
  tp?: number | null;
  risk_pct?: number | null;
}

export interface RiskPreview {
  decision: string;
  reasons: string[];
  warnings: string[];
  sizing: {
    entry_price: number | null;
    estimated_loss: number | null;
    estimated_reward: number | null;
    sized_risk_pct: number | null;
    max_volume_for_risk: number | null;
    current_portfolio_risk_pct: number | null;
    projected_portfolio_risk_pct: number | null;
  };
  limits: {
    max_risk_per_trade_pct: number;
    max_portfolio_risk_pct: number;
    max_order_volume_lots: number;
  };
}

export interface Mt5Configuration {
  enabled: boolean;
  bridge_type: "mock" | "ea_socket";
  host: string;
  port: number;
  timeout_sec: number;
  heartbeat_max_age_sec: number;
  expected_login: number | null;
  expected_server: string | null;
  expected_account_type: "DEMO" | "REAL" | "UNKNOWN";
  source?: "database" | "environment";
  stores_password?: boolean;
  ea_shared_secret_configured?: boolean;
  updated_by?: string | null;
  updated_at?: string | null;
}

export interface StrategyPresetConfiguration {
  enabled: boolean;
  symbol: string;
  preset_name: string;
  d40_value: number;
  d20_value: number;
  reward_risk_ratio: number;
  risk_pct: number;
  require_news_clear: boolean;
  signal_definition_confirmed: boolean;
  source?: "database" | "environment";
  updated_by?: string | null;
  updated_at?: string | null;
}

export interface TradeProposal {
  id: number;
  status: string;
  symbol: string;
  side: "BUY" | "SELL";
  entry_price: number;
  sl: number;
  tp: number;
  volume: number;
  risk_pct: number;
  strategy_name: string;
  strategy_reason: string;
  ai_summary: string | null;
  ai_confidence: number | null;
  risk_decision: string;
  risk_reasons: string[];
  risk_warnings: string[];
  created_at: string;
  expires_at: string;
}

export type AnalysisCapability =
  | "news_search"
  | "economic_calendar"
  | "chart_market"
  | "volatility_session"
  | "proposal_explanation"
  | "loss_review";

export interface DiscoveredTool {
  name: string;
  title: string | null;
  description: string;
}

export interface AnalysisProvider {
  id: number | null;
  display_name: string;
  provider_type: "mcp" | "claude" | "openai" | "local";
  enabled: boolean;
  transport: "streamable_http" | "sse" | null;
  endpoint: string | null;
  model_name: string | null;
  web_search_enabled: boolean;
  secret_ref: string | null;
  secret_configured?: boolean;
  timeout_sec: number;
  priority: number;
  capabilities: AnalysisCapability[];
  allowed_tools: string[];
  capability_tools: Partial<Record<AnalysisCapability, string>>;
  discovered_tools: DiscoveredTool[];
  discovered_models: string[];
  health: "HEALTHY" | "UNHEALTHY" | "UNKNOWN";
  latency_ms: number | null;
  last_checked_at: string | null;
  last_error: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AnalysisProviderMetadata {
  provider_types: AnalysisProvider["provider_type"][];
  mcp_transports: Array<"streamable_http" | "sse">;
  capabilities: AnalysisCapability[];
  secret_ref_prefix: string;
  health_checks: {
    enabled: boolean;
    interval_seconds: number;
    batch_size: number;
  };
}

export interface ProviderHealthBatchResult {
  periodic_enabled: boolean;
  interval_seconds: number;
  eligible: number;
  due: number;
  checked: number;
  healthy: number;
  unhealthy: number;
  skipped: number;
  results: Array<{
    provider_id: number;
    display_name: string;
    provider_type: AnalysisProvider["provider_type"];
    health: "HEALTHY" | "UNHEALTHY";
    latency_ms: number | null;
    discovered_tool_names: string[];
    discovered_models: string[];
    error: string | null;
  }>;
}

export type AnalysisRouting = Record<
  AnalysisCapability,
  Array<{
    id: number;
    display_name: string;
    provider_type: AnalysisProvider["provider_type"];
    priority: number;
  }>
>;

function providerPayload(provider: AnalysisProvider) {
  return {
    display_name: provider.display_name,
    provider_type: provider.provider_type,
    enabled: provider.enabled,
    transport: provider.provider_type === "mcp" ? provider.transport : null,
    endpoint: provider.endpoint || null,
    model_name:
      provider.provider_type === "local" || provider.provider_type === "openai"
        ? provider.model_name
        : null,
    web_search_enabled:
      (provider.provider_type === "local" || provider.provider_type === "openai")
      && provider.web_search_enabled,
    secret_ref: provider.secret_ref || null,
    timeout_sec: provider.timeout_sec,
    priority: provider.priority,
    capabilities: provider.capabilities,
    allowed_tools: provider.allowed_tools,
    capability_tools: provider.capability_tools,
  };
}

export interface MarketDataConfiguration {
  enabled: boolean;
  provider: "mt5" | "alpaca" | "disabled";
  endpoint: string;
  feed: "iex" | "sip" | "delayed_sip";
  api_key_ref: string | null;
  api_secret_ref: string | null;
  default_symbols: string[];
  max_symbols: number;
  timeout_sec: number;
  source?: "database" | "environment";
  feed_status?: string;
  api_key_configured?: boolean;
  api_secret_configured?: boolean;
  updated_by?: string | null;
  updated_at?: string | null;
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketCandles {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  error?: string;
}

export interface AnalysisRunResult {
  available: boolean;
  capability: AnalysisCapability;
  correlation_id: string;
  summary: string | null;
  confidence: number;
  provider_id: number | null;
  provider_name: string | null;
  provider_type: AnalysisProvider["provider_type"] | null;
  model_or_tool: string | null;
  attempts: Array<{
    provider_id: number | null;
    provider_name: string | null;
    provider_type: string | null;
    success: boolean;
    latency_ms: number | null;
    model_or_tool: string | null;
    error: string | null;
  }>;
}

export const api = {
  authStatus: () =>
    http.get<AuthStatus>("/api/auth/status").then((r) => r.data),
  login: (mt5_login: number, app_password: string) =>
    http
      .post("/api/auth/login", { mt5_login, app_password })
      .then((r) => r.data),
  bootstrapUser: (payload: {
    mt5_login: number;
    app_password: string;
    display_name: string;
    mt5_server: string;
    account_type: "DEMO" | "REAL";
  }) => http.post("/api/auth/bootstrap", payload).then((r) => r.data),
  logout: () => http.post("/api/auth/logout").then((r) => r.data),
  health: () => http.get("/health").then((r) => r.data),
  dashboard: () => http.get("/api/dashboard").then((r) => r.data),
  account: () => http.get("/api/account").then((r) => r.data),
  accountConfiguration: () =>
    http.get<Mt5Configuration>("/api/account/configuration").then((r) => r.data),
  updateAccountConfiguration: (config: Mt5Configuration) => {
    const payload = {
      enabled: config.enabled,
      bridge_type: config.bridge_type,
      host: config.host,
      port: config.port,
      timeout_sec: config.timeout_sec,
      heartbeat_max_age_sec: config.heartbeat_max_age_sec,
      expected_login: config.expected_login || null,
      expected_server: config.expected_server || null,
      expected_account_type: config.expected_account_type,
    };
    return http.put("/api/account/configuration", payload).then((r) => r.data);
  },
  testAccountConfiguration: () =>
    http
      .post("/api/account/configuration/test", undefined, { timeout: 65000 })
      .then((r) => r.data),
  strategyConfiguration: () =>
    http.get<StrategyPresetConfiguration>("/api/strategy/configuration").then((r) => r.data),
  updateStrategyConfiguration: (config: StrategyPresetConfiguration) => {
    const payload = {
      enabled: config.enabled,
      symbol: config.symbol,
      preset_name: config.preset_name,
      d40_value: config.d40_value,
      d20_value: config.d20_value,
      reward_risk_ratio: config.reward_risk_ratio,
      risk_pct: config.risk_pct,
      require_news_clear: config.require_news_clear,
      signal_definition_confirmed: config.signal_definition_confirmed,
    };
    return http.put<StrategyPresetConfiguration>("/api/strategy/configuration", payload)
      .then((r) => r.data);
  },
  proposals: () => http.get<TradeProposal[]>("/api/proposals").then((r) => r.data),
  generateProposal: (payload: {
    side: "BUY" | "SELL";
    sl: number;
    volume: number | null;
    strategy_reason: string;
  }) => http.post<TradeProposal>("/api/proposals", payload).then((r) => r.data),
  submitProposal: (proposalId: number) =>
    http.post<OrderResult>(`/api/proposals/${proposalId}/submit`).then((r) => r.data),
  evaluateSignal: () => http.post("/api/strategy/evaluate-signal").then((r) => r.data),
  backtestSignal: (count = 500) =>
    http.post("/api/strategy/backtest", null, { params: { count } }).then((r) => r.data),
  riskStatus: (params?: Record<string, unknown>) =>
    http.get("/api/risk/status", { params }).then((r) => r.data),
  previewOrder: (payload: OrderTicket) =>
    http.post<RiskPreview>("/api/risk/preview", payload).then((r) => r.data),

  submitOrder: (payload: OrderTicket) =>
    http.post<OrderResult>("/api/orders/submit", payload).then((r) => r.data),
  approveOrder: (idempotency_key: string) =>
    http.post<OrderResult>("/api/orders/approve", { idempotency_key }).then((r) => r.data),
  rejectOrder: (idempotency_key: string) =>
    http.post<OrderResult>("/api/orders/reject", { idempotency_key }).then((r) => r.data),
  reconcileOrder: (idempotency_key: string) =>
    http.post<OrderResult>("/api/orders/reconcile", { idempotency_key }).then((r) => r.data),
  recentOrders: () => http.get("/api/orders/recent").then((r) => r.data),
  pendingApprovals: () => http.get("/api/orders/pending-approval").then((r) => r.data),

  marketCandles: (symbol: string, timeframe: string, count = 200) =>
    http
      .get<MarketCandles>("/api/market/candles", {
        params: { symbol, timeframe, count },
      })
      .then((r) => r.data),

  logs: () => http.get("/api/logs").then((r) => r.data),
  audit: () => http.get("/api/logs/audit").then((r) => r.data),
  riskLogs: () => http.get("/api/logs/risk").then((r) => r.data),

  historyTrades: () => http.get("/api/history/trades").then((r) => r.data),
  historySummary: () => http.get("/api/history/summary").then((r) => r.data),
  historyDaily: () => http.get("/api/history/daily").then((r) => r.data),
  historyReview: () => http.get("/api/history/review").then((r) => r.data),
  saveTradeReview: (ticket: number, note: string) =>
    http.post(`/api/history/review/${ticket}`, { note }).then((r) => r.data),
  analyzeTradeReview: (ticket: number) =>
    http
      .post<AnalysisRunResult>(`/api/history/review/${ticket}/analyze`)
      .then((r) => r.data),
  historyBackfill: (days = 30) =>
    http.post("/api/history/backfill", null, { params: { days } }).then((r) => r.data),

  workflowStatus: () => http.get("/api/workflow/status").then((r) => r.data),
  workflowStart: () => http.post("/api/workflow/start").then((r) => r.data),
  workflowStop: () => http.post("/api/workflow/stop").then((r) => r.data),
  workflowRun: () => http.post("/api/workflow/run").then((r) => r.data),

  analysisProviderMetadata: () =>
    http
      .get<AnalysisProviderMetadata>("/api/settings/analysis-providers/metadata")
      .then((r) => r.data),
  analysisProviders: () =>
    http
      .get<AnalysisProvider[]>("/api/settings/analysis-providers")
      .then((r) => r.data),
  analysisProviderRouting: () =>
    http
      .get<AnalysisRouting>("/api/settings/analysis-providers/routing")
      .then((r) => r.data),
  createAnalysisProvider: (provider: AnalysisProvider) =>
    http
      .post<AnalysisProvider>(
        "/api/settings/analysis-providers",
        providerPayload(provider),
      )
      .then((r) => r.data),
  updateAnalysisProvider: (provider: AnalysisProvider) =>
    http
      .put<AnalysisProvider>(
        `/api/settings/analysis-providers/${provider.id}`,
        providerPayload(provider),
      )
      .then((r) => r.data),
  testAnalysisProvider: (providerId: number) =>
    http
      .post<AnalysisProvider>(
        `/api/settings/analysis-providers/${providerId}/test`,
        undefined,
        { timeout: 130000 },
      )
      .then((r) => r.data),
  testEnabledAnalysisProviders: () =>
    http
      .post<ProviderHealthBatchResult>(
        "/api/settings/analysis-providers/health-check",
        undefined,
        { timeout: 130000 },
      )
      .then((r) => r.data),
  deleteAnalysisProvider: (providerId: number) =>
    http.delete(`/api/settings/analysis-providers/${providerId}`),
  runAnalysis: (
    capability: AnalysisCapability,
    prompt: string,
    context: Record<string, unknown>,
  ) =>
    http
      .post<AnalysisRunResult>(
        "/api/analysis/run",
        { capability, prompt, context },
        { timeout: 130000 },
      )
      .then((r) => r.data),
  analysisSnapshots: () =>
    http.get("/api/analysis/snapshots").then((r) => r.data),
  marketDataConfiguration: () =>
    http
      .get<MarketDataConfiguration>("/api/settings/market-data")
      .then((r) => r.data),
  updateMarketDataConfiguration: (config: MarketDataConfiguration) =>
    http
      .put<MarketDataConfiguration>("/api/settings/market-data", {
        enabled: config.enabled,
        provider: config.provider,
        endpoint: config.endpoint,
        feed: config.feed,
        api_key_ref: config.api_key_ref || null,
        api_secret_ref: config.api_secret_ref || null,
        default_symbols: config.default_symbols,
        max_symbols: config.max_symbols,
        timeout_sec: config.timeout_sec,
      })
      .then((r) => r.data),
  testMarketDataConfiguration: () =>
    http
      .post("/api/settings/market-data/test", undefined, { timeout: 65000 })
      .then((r) => r.data),
};
