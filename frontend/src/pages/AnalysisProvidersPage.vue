<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  api,
  type AnalysisCapability,
  type AnalysisProvider,
  type AnalysisProviderMetadata,
  type AnalysisRouting,
} from "../api/client";

const capabilityLabels: Record<AnalysisCapability, string> = {
  news_search: "News search",
  economic_calendar: "Economic calendar",
  chart_market: "Chart / market",
  volatility_session: "Volatility / session",
  proposal_explanation: "Proposal explanation",
  loss_review: "Losing-trade review",
};

const providers = ref<AnalysisProvider[]>([]);
const metadata = ref<AnalysisProviderMetadata | null>(null);
const routing = ref<AnalysisRouting | null>(null);
const draft = ref<AnalysisProvider | null>(null);
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const checkingAll = ref(false);
const deleting = ref(false);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

const selectedId = computed(() => draft.value?.id ?? null);

function blankProvider(): AnalysisProvider {
  return {
    id: null,
    display_name: "",
    provider_type: "mcp",
    enabled: false,
    transport: "streamable_http",
    endpoint: "http://127.0.0.1:8001/mcp",
    model_name: null,
    web_search_enabled: false,
    secret_ref: null,
    timeout_sec: 10,
    priority: 100,
    capabilities: [],
    allowed_tools: [],
    capability_tools: {},
    discovered_tools: [],
    discovered_models: [],
    health: "UNKNOWN",
    latency_ms: null,
    last_checked_at: null,
    last_error: null,
  };
}

function copyProvider(provider: AnalysisProvider): AnalysisProvider {
  return JSON.parse(JSON.stringify(provider)) as AnalysisProvider;
}

function cloneProvider(provider: AnalysisProvider) {
  draft.value = copyProvider(provider);
  error.value = null;
  message.value = null;
}

function providerTypeChanged() {
  if (!draft.value) return;
  draft.value.transport =
    draft.value.provider_type === "mcp" ? "streamable_http" : null;
  if (draft.value.provider_type === "local") {
    draft.value.endpoint = "http://127.0.0.1:3000";
    draft.value.model_name ||= "qwen3.5:9b";
    draft.value.secret_ref ||= "ANALYSIS_PROVIDER_OPEN_WEBUI_KEY";
  } else if (draft.value.provider_type === "openai") {
    draft.value.endpoint = "https://api.openai.com/v1";
    draft.value.model_name ||= "gpt-5.5";
    draft.value.secret_ref ||= "ANALYSIS_PROVIDER_OPENAI_KEY";
    draft.value.allowed_tools = [];
    draft.value.capability_tools = {};
  }
}

function errorText(value: any, fallback: string) {
  const detail = value?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item.msg).join("; ");
  }
  return detail ?? value?.message ?? fallback;
}

async function load(preferredId?: number | null) {
  loading.value = true;
  try {
    [metadata.value, providers.value, routing.value] = await Promise.all([
      api.analysisProviderMetadata(),
      api.analysisProviders(),
      api.analysisProviderRouting(),
    ]);
    const id = preferredId ?? selectedId.value;
    const selected = providers.value.find((provider) => provider.id === id);
    draft.value = selected
      ? copyProvider(selected)
      : providers.value.length
        ? copyProvider(providers.value[0])
        : blankProvider();
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Failed to load analysis providers");
  } finally {
    loading.value = false;
  }
}

function toggleCapability(capability: AnalysisCapability) {
  if (!draft.value) return;
  const index = draft.value.capabilities.indexOf(capability);
  if (index >= 0) {
    draft.value.capabilities.splice(index, 1);
    delete draft.value.capability_tools[capability];
  } else {
    draft.value.capabilities.push(capability);
  }
}

function mappedTool(capability: AnalysisCapability) {
  return draft.value?.capability_tools[capability] ?? "";
}

function updateMappedTool(capability: AnalysisCapability, event: Event) {
  if (!draft.value) return;
  const value = (event.target as HTMLSelectElement).value;
  if (value) {
    draft.value.capability_tools[capability] = value;
  } else {
    delete draft.value.capability_tools[capability];
  }
}

function toggleTool(toolName: string) {
  if (!draft.value) return;
  const index = draft.value.allowed_tools.indexOf(toolName);
  if (index >= 0) {
    draft.value.allowed_tools.splice(index, 1);
  } else {
    draft.value.allowed_tools.push(toolName);
  }
}

function updateAllowedTools(event: Event) {
  if (!draft.value) return;
  const target = event.target as HTMLTextAreaElement;
  draft.value.allowed_tools = target.value
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean);
}

async function save() {
  if (!draft.value) return;
  if (!draft.value.display_name.trim()) {
    error.value = "Display name is required.";
    return;
  }
  saving.value = true;
  message.value = null;
  try {
    const saved = draft.value.id
      ? await api.updateAnalysisProvider(draft.value)
      : await api.createAnalysisProvider(draft.value);
    message.value = "Provider configuration saved. Run a connection test before routing it.";
    await load(saved.id);
  } catch (e: any) {
    error.value = errorText(e, "Failed to save provider");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  if (!draft.value?.id) return;
  testing.value = true;
  message.value = null;
  try {
    const tested = await api.testAnalysisProvider(draft.value.id);
    message.value =
      tested.health === "HEALTHY"
        ? tested.provider_type === "local"
          ? `Connection healthy. Open WebUI returned ${tested.discovered_models.length} model(s).`
          : `Connection healthy. Discovered ${tested.discovered_tools.length} tool(s).`
        : `Connection failed: ${tested.last_error ?? "Unknown provider error"}`;
    await load(tested.id);
  } catch (e: any) {
    error.value = errorText(e, "Provider connection test failed");
  } finally {
    testing.value = false;
  }
}

async function testEnabledProviders() {
  checkingAll.value = true;
  error.value = null;
  message.value = null;
  try {
    const result = await api.testEnabledAnalysisProviders();
    message.value = result.checked
      ? `Checked ${result.checked} provider(s): ${result.healthy} healthy, ${result.unhealthy} unhealthy.`
      : "No enabled providers to check.";
    await load(selectedId.value);
  } catch (e: any) {
    error.value = errorText(e, "Provider health check failed");
  } finally {
    checkingAll.value = false;
  }
}

async function removeProvider() {
  if (!draft.value?.id) return;
  if (!window.confirm(`Delete provider "${draft.value.display_name}"?`)) return;
  deleting.value = true;
  try {
    await api.deleteAnalysisProvider(draft.value.id);
    message.value = "Provider deleted.";
    draft.value = null;
    await load();
  } catch (e: any) {
    error.value = errorText(e, "Failed to delete provider");
  } finally {
    deleting.value = false;
  }
}

function fmtDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Never";
}

onMounted(() => load());
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Analysis Providers</h2>
      <p class="sub">Configure advisory AI and MCP sources. Execution remains isolated in OrderService.</p>
    </div>
    <div class="head-actions">
      <button
        class="btn secondary sm"
        @click="testEnabledProviders"
        :disabled="loading || checkingAll"
      >
        <span v-if="checkingAll" class="spin"></span>
        Check enabled providers
      </button>
      <button class="btn secondary sm" @click="load()" :disabled="loading">Refresh</button>
    </div>
  </div>

  <div v-if="error" class="notice page-notice">{{ error }}</div>
  <div v-if="message" class="notice success page-notice">{{ message }}</div>

  <div v-if="loading" class="provider-layout">
    <section class="panel"><div class="skeleton sk-line"></div><div class="skeleton sk-line"></div></section>
    <section class="panel"><div class="skeleton sk-line"></div><div class="skeleton sk-line"></div><div class="skeleton sk-line"></div></section>
  </div>

  <template v-else-if="draft && metadata">
    <div class="notice neutral safety-copy">
      MCP output is untrusted advisory data. Only enabled, healthy providers enter a capability route,
      and no provider can call MT5 or place an order directly.
      <span v-if="metadata.health_checks.enabled">
        Enabled providers are checked automatically every
        {{ metadata.health_checks.interval_seconds }} seconds while the workflow scheduler runs.
      </span>
      <span v-else>Automatic provider health checks are disabled by configuration.</span>
    </div>

    <div class="provider-layout">
      <aside class="panel provider-list">
        <div class="panel-head">
          <span class="panel-title">Providers</span>
          <button class="btn sm" @click="draft = blankProvider()">New</button>
        </div>
        <button
          v-for="provider in providers"
          :key="provider.id!"
          class="provider-row"
          :class="{ selected: selectedId === provider.id }"
          @click="cloneProvider(provider)"
        >
          <span class="provider-row-main">
            <strong>{{ provider.display_name }}</strong>
            <span class="muted">{{ provider.provider_type.toUpperCase() }} · priority {{ provider.priority }}</span>
          </span>
          <span class="badge" :class="provider.enabled ? provider.health : 'UNKNOWN'">
            {{ provider.enabled ? provider.health : "DISABLED" }}
          </span>
        </button>
        <div v-if="!providers.length" class="empty compact">
          <div class="title">No providers configured</div>
          <p>Create an MCP or AI provider to begin.</p>
        </div>
      </aside>

      <section class="panel editor">
        <div class="panel-head">
          <div>
            <span class="panel-title">{{ draft.id ? "Provider Configuration" : "New Provider" }}</span>
            <p v-if="draft.id" class="editor-meta">Last checked: {{ fmtDate(draft.last_checked_at) }}</p>
          </div>
          <label class="switch-row">
            <input v-model="draft.enabled" type="checkbox" />
            <span>Enabled</span>
          </label>
        </div>

        <div class="form-grid">
          <div class="field">
            <label>Display name</label>
            <input v-model.trim="draft.display_name" placeholder="Gold news MCP" />
          </div>
          <div class="field">
            <label>Provider type</label>
            <select v-model="draft.provider_type" @change="providerTypeChanged">
              <option v-for="type in metadata.provider_types" :key="type" :value="type">
                {{ type.toUpperCase() }}
              </option>
            </select>
          </div>
          <div v-if="draft.provider_type === 'mcp'" class="field">
            <label>Transport</label>
            <select v-model="draft.transport">
              <option value="streamable_http">Streamable HTTP</option>
              <option value="sse">SSE (legacy)</option>
            </select>
          </div>
          <div class="field">
            <label>Priority</label>
            <input v-model.number="draft.priority" type="number" min="1" max="1000" />
          </div>
          <div class="field span-2">
            <label>Endpoint</label>
            <input
              v-model.trim="draft.endpoint"
              :placeholder="draft.provider_type === 'local'
                ? 'http://127.0.0.1:3000'
                : 'https://provider.example.com/mcp'"
            />
          </div>
          <div v-if="draft.provider_type === 'local' || draft.provider_type === 'openai'" class="field">
            <label>{{ draft.provider_type === "local" ? "Open WebUI model" : "OpenAI model" }}</label>
            <input
              v-model.trim="draft.model_name"
              list="analysis-models"
              :placeholder="draft.provider_type === 'local' ? 'qwen3.5:9b' : 'gpt-5.5'"
            />
            <datalist id="analysis-models">
              <option v-for="model in draft.discovered_models" :key="model" :value="model" />
            </datalist>
            <small>Test the connection to verify that this model is available.</small>
          </div>
          <div class="field">
            <label>Secret environment reference</label>
            <input
              v-model.trim="draft.secret_ref"
              :placeholder="
                draft.provider_type === 'local'
                  ? 'ANALYSIS_PROVIDER_OPEN_WEBUI_KEY'
                  : draft.provider_type === 'openai'
                    ? 'ANALYSIS_PROVIDER_OPENAI_KEY'
                    : 'MCP_PROVIDER_NEWS_TOKEN'
              "
            />
            <small>
              Secret value is never stored.
              <span v-if="draft.id">{{ draft.secret_configured ? "Reference is configured." : "Reference has no value." }}</span>
            </small>
          </div>
          <div class="field">
            <label>Timeout (seconds)</label>
            <input v-model.number="draft.timeout_sec" type="number" min="1" max="120" step="1" />
          </div>
        </div>

        <label
          v-if="draft.provider_type === 'local' || draft.provider_type === 'openai'"
          class="switch-row local-option"
        >
          <input v-model="draft.web_search_enabled" type="checkbox" />
          <span>
            Enable {{ draft.provider_type === "local" ? "Open WebUI" : "OpenAI" }} web search
            <small>Search remains advisory and must not be used as an execution price feed.</small>
          </span>
        </label>

        <fieldset class="choice-group">
          <legend>Assigned capabilities</legend>
          <label v-for="capability in metadata.capabilities" :key="capability" class="check-row">
            <input
              type="checkbox"
              :checked="draft.capabilities.includes(capability)"
              @change="toggleCapability(capability)"
            />
            <span>{{ capabilityLabels[capability] }}</span>
          </label>
        </fieldset>

        <section
          v-if="draft.provider_type === 'mcp' && draft.capabilities.length"
          class="tool-section"
        >
          <div class="panel-head">
            <div>
              <span class="panel-title">Capability Tool Mapping</span>
              <p class="editor-meta">Choose exactly which allowed MCP tool handles each capability.</p>
            </div>
          </div>
          <div class="mapping-grid">
            <div v-for="capability in draft.capabilities" :key="capability" class="field">
              <label>{{ capabilityLabels[capability] }}</label>
              <select
                :value="mappedTool(capability)"
                @change="updateMappedTool(capability, $event)"
              >
                <option value="">Select allowed tool</option>
                <option v-for="tool in draft.allowed_tools" :key="tool" :value="tool">
                  {{ tool }}
                </option>
              </select>
            </div>
          </div>
        </section>

        <section
          v-if="draft.provider_type === 'mcp' || draft.provider_type === 'local'"
          class="tool-section"
        >
          <div class="panel-head">
            <div>
              <span class="panel-title">
                {{ draft.provider_type === "local" ? "Open WebUI Tool IDs" : "Discovered Tools / Allowlist" }}
              </span>
              <p class="editor-meta">
                Only IDs in this allowlist may be sent to the provider.
              </p>
            </div>
          </div>
          <div v-if="draft.discovered_tools.length" class="tool-list">
            <label v-for="tool in draft.discovered_tools" :key="tool.name" class="tool-row">
              <input
                type="checkbox"
                :checked="draft.allowed_tools.includes(tool.name)"
                @change="toggleTool(tool.name)"
              />
              <span>
                <strong class="mono">{{ tool.name }}</strong>
                <small>{{ tool.description || "No description provided" }}</small>
              </span>
            </label>
          </div>
          <div v-else-if="draft.provider_type === 'local'" class="field">
            <label>Allowed tool IDs (one per line)</label>
            <textarea
              :value="draft.allowed_tools.join('\n')"
              rows="4"
              placeholder="server:mcp:trusted-search"
              @input="updateAllowedTools"
            ></textarea>
            <small>Use IDs configured in Open WebUI. Leave empty to deny all explicit tools.</small>
          </div>
          <p v-else class="muted">Save and test the MCP provider to discover tools.</p>
        </section>

        <div v-if="draft.id" class="health-panel">
          <div class="kv"><span class="label">Health</span><span class="value"><span class="badge" :class="draft.health">{{ draft.health }}</span></span></div>
          <div class="kv"><span class="label">Latency</span><span class="value mono">{{ draft.latency_ms == null ? "—" : `${draft.latency_ms} ms` }}</span></div>
          <div v-if="draft.last_error" class="kv"><span class="label">Last error</span><span class="value error-copy">{{ draft.last_error }}</span></div>
        </div>

        <div class="editor-actions">
          <button v-if="draft.id" class="btn danger ghost-danger" @click="removeProvider" :disabled="deleting || saving || testing">
            Delete
          </button>
          <span class="action-spacer"></span>
          <button class="btn secondary" @click="testConnection" :disabled="!draft.id || testing || saving">
            <span v-if="testing" class="spin"></span>
            Test connection
          </button>
          <button class="btn" @click="save" :disabled="saving || testing">
            <span v-if="saving" class="spin"></span>
            Save provider
          </button>
        </div>
        <p v-if="!draft.id" class="muted action-note">Save before running connection test and tool discovery.</p>
      </section>
    </div>

    <section v-if="routing" class="panel routing-panel">
      <div class="panel-head">
        <span class="panel-title">Active Capability Routing</span>
        <span class="muted">Enabled + healthy only</span>
      </div>
      <div class="routing-grid">
        <div v-for="capability in metadata.capabilities" :key="capability" class="route-card">
          <strong>{{ capabilityLabels[capability] }}</strong>
          <div v-if="routing[capability]?.length" class="route-chain">
            <span v-for="(provider, index) in routing[capability]" :key="provider.id">
              {{ index + 1 }}. {{ provider.display_name }}
            </span>
          </div>
          <span v-else class="badge BLOCK">NO HEALTHY PROVIDER</span>
        </div>
      </div>
    </section>
  </template>
</template>

<style scoped>
.page-notice { margin-bottom: var(--sp-5); }
.head-actions { display: flex; gap: var(--sp-3); }
.notice.success { background: var(--allow-bg); color: var(--allow-fg); }
.notice.neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
.safety-copy { margin-bottom: var(--sp-6); }
.provider-layout {
  display: grid;
  grid-template-columns: minmax(230px, 0.65fr) minmax(0, 1.8fr);
  gap: var(--sp-6);
  align-items: start;
}
.provider-list { padding: var(--sp-5); }
.provider-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: var(--sp-5);
  color: var(--ink);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  cursor: pointer;
  text-align: left;
}
.provider-row:hover { background: var(--surface-2); }
.provider-row.selected { background: var(--surface-2); border-color: var(--border-strong); }
.provider-row-main { display: flex; min-width: 0; flex-direction: column; gap: var(--sp-1); }
.provider-row-main strong { overflow: hidden; text-overflow: ellipsis; }
.provider-row-main .muted { font-size: var(--text-xs); }
.empty.compact { padding: var(--sp-7) var(--sp-4); }
.editor-meta { margin-top: var(--sp-2); color: var(--ink-muted); font-size: var(--text-xs); }
.switch-row, .check-row, .tool-row { display: flex; align-items: center; gap: var(--sp-4); cursor: pointer; }
.switch-row input, .check-row input, .tool-row input { width: auto; flex: 0 0 auto; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--sp-5); }
.span-2 { grid-column: span 2; }
.field small, .tool-row small { display: block; margin-top: var(--sp-2); color: var(--ink-muted); }
.choice-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-4);
  margin: var(--sp-5) 0 var(--sp-7);
  padding: var(--sp-6);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
}
.choice-group legend { padding: 0 var(--sp-3); color: var(--ink-muted); font-size: var(--text-sm); font-weight: 600; }
.tool-section { margin-top: var(--sp-5); padding-top: var(--sp-6); border-top: 1px solid var(--border); }
.local-option { margin: var(--sp-5) 0; align-items: flex-start; }
.local-option small { display: block; margin-top: var(--sp-1); color: var(--ink-muted); }
.tool-list { display: grid; gap: var(--sp-3); }
.mapping-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sp-4); }
.tool-row { align-items: flex-start; padding: var(--sp-4); background: var(--surface-2); border-radius: var(--r-md); }
.health-panel { margin-top: var(--sp-7); padding: var(--sp-5); background: var(--surface-2); border-radius: var(--r-md); }
.error-copy { max-width: 70%; color: var(--block-fg); overflow-wrap: anywhere; }
.editor-actions { display: flex; gap: var(--sp-4); margin-top: var(--sp-7); }
.action-spacer { flex: 1; }
.action-note { margin-top: var(--sp-3); text-align: right; font-size: var(--text-xs); }
.routing-panel { margin-top: var(--sp-6); }
.routing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--sp-4); }
.route-card { display: flex; min-height: 92px; flex-direction: column; gap: var(--sp-4); padding: var(--sp-5); background: var(--surface-2); border-radius: var(--r-md); }
.route-chain { display: flex; flex-direction: column; color: var(--ink-muted); font-size: var(--text-sm); }
@media (max-width: 900px) {
  .provider-layout { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .page-head { align-items: flex-start; gap: var(--sp-4); }
  .head-actions { width: 100%; flex-direction: column; }
  .head-actions .btn { width: 100%; }
  .form-grid, .choice-group, .mapping-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: auto; }
  .editor-actions { flex-direction: column-reverse; }
  .editor-actions .btn { width: 100%; }
  .action-spacer { display: none; }
}
</style>
