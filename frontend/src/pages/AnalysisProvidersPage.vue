<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  api,
  type AnalysisCapability,
  type AnalysisProvider,
  type AnalysisProviderMetadata,
  type AnalysisRouting,
} from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Kv from "../components/ui/Kv.vue";
import Field from "../components/ui/Field.vue";
import Switch from "../components/ui/Switch.vue";
import Toggle from "../components/ui/Toggle.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import Icon from "../components/ui/Icon.vue";
import { badgeClass } from "../components/ui/badge";

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
    id: null, display_name: "", provider_type: "mcp", enabled: false,
    transport: "streamable_http", endpoint: "http://127.0.0.1:8001/mcp", model_name: null,
    web_search_enabled: false, secret_ref: null, timeout_sec: 10, priority: 100,
    capabilities: [], allowed_tools: [], capability_tools: {}, discovered_tools: [],
    discovered_models: [], health: "UNKNOWN", latency_ms: null, last_checked_at: null, last_error: null,
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
  draft.value.transport = draft.value.provider_type === "mcp" ? "streamable_http" : null;
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
  if (Array.isArray(detail)) return detail.map((item: any) => item.msg).join("; ");
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
      : providers.value.length ? copyProvider(providers.value[0]) : blankProvider();
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
  if (value) draft.value.capability_tools[capability] = value;
  else delete draft.value.capability_tools[capability];
}
function toggleTool(toolName: string) {
  if (!draft.value) return;
  const index = draft.value.allowed_tools.indexOf(toolName);
  if (index >= 0) draft.value.allowed_tools.splice(index, 1);
  else draft.value.allowed_tools.push(toolName);
}
function updateAllowedTools(event: Event) {
  if (!draft.value) return;
  const target = event.target as HTMLTextAreaElement;
  draft.value.allowed_tools = target.value.split("\n").map((v) => v.trim()).filter(Boolean);
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
  <div class="stack">
    <PageHead title="Analysis Providers" sub="AI / MCP providers and capability routing · deny-by-default">
      <template #actions>
        <Btn sm variant="secondary" icon="wifi" :loading="checkingAll" :disabled="loading || checkingAll" @click="testEnabledProviders">Check enabled</Btn>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load()">Refresh</Btn>
        <Btn sm icon="plus" @click="draft = blankProvider()">New provider</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>
    <Notice v-if="message" tone="success">{{ message }}</Notice>

    <div v-if="loading && !metadata" class="prov-layout">
      <div class="panel panel-pad"><div class="sk-line" /><div class="sk-line" style="margin-top: 8px" /></div>
      <div class="panel panel-pad"><div class="sk-line" /><div class="sk-line" style="margin-top: 8px" /><div class="sk-line" style="margin-top: 8px" /></div>
    </div>

    <template v-else-if="draft && metadata">
      <Notice tone="neutral">
        MCP output is untrusted advisory data. Only enabled, healthy providers enter a capability route, and no provider can call MT5 or place an order directly.
        <template v-if="metadata.health_checks.enabled"> Enabled providers are checked automatically every {{ metadata.health_checks.interval_seconds }}s while the workflow scheduler runs.</template>
        <template v-else> Automatic provider health checks are disabled by configuration.</template>
      </Notice>

      <div class="prov-layout">
        <Panel title="Providers" :pad="false">
          <div style="padding: var(--sp-4)" class="stack-sm">
            <div
              v-for="provider in providers"
              :key="provider.id!"
              class="prov-item"
              :data-on="selectedId === provider.id"
              @click="cloneProvider(provider)"
            >
              <div class="pn">{{ provider.display_name }}<Badge :tone="provider.enabled ? badgeClass(provider.health === 'HEALTHY' ? 'OK' : provider.health) : ''" no-dot>{{ provider.enabled ? provider.health : "DISABLED" }}</Badge></div>
              <div class="pm">{{ provider.provider_type }} · priority {{ provider.priority }}</div>
            </div>
            <EmptyState v-if="!providers.length" icon="providers" title="No providers configured" desc="Create an MCP or AI provider to begin." />
          </div>
        </Panel>

        <div class="stack">
          <Panel :title="draft.id ? `Configuration · ${draft.display_name || 'provider'}` : 'New provider'">
            <template #action><Switch :checked="draft.enabled" @change="draft.enabled = $event" /></template>
            <div class="stack">
              <p v-if="draft.id" class="faint" style="font-size: var(--text-xs); margin: 0">Last checked: {{ fmtDate(draft.last_checked_at) }}</p>
              <div class="form-grid">
                <Field label="Display name"><input v-model.trim="draft.display_name" placeholder="Gold news MCP" /></Field>
                <Field label="Provider type">
                  <select v-model="draft.provider_type" @change="providerTypeChanged">
                    <option v-for="type in metadata.provider_types" :key="type" :value="type">{{ type.toUpperCase() }}</option>
                  </select>
                </Field>
                <Field v-if="draft.provider_type === 'mcp'" label="Transport">
                  <select v-model="draft.transport">
                    <option value="streamable_http">Streamable HTTP</option>
                    <option value="sse">SSE (legacy)</option>
                  </select>
                </Field>
                <Field label="Priority"><input class="mono" v-model.number="draft.priority" type="number" min="1" max="1000" /></Field>
                <Field class="full" label="Endpoint" hint="HTTPS required for remote hosts">
                  <input class="mono" v-model.trim="draft.endpoint" :placeholder="draft.provider_type === 'local' ? 'http://127.0.0.1:3000' : 'https://provider.example.com/mcp'" />
                </Field>
                <Field v-if="draft.provider_type === 'local' || draft.provider_type === 'openai'" :label="draft.provider_type === 'local' ? 'Open WebUI model' : 'OpenAI model'" hint="Test the connection to verify availability">
                  <input class="mono" v-model.trim="draft.model_name" list="analysis-models" :placeholder="draft.provider_type === 'local' ? 'qwen3.5:9b' : 'gpt-5.5'" />
                  <datalist id="analysis-models"><option v-for="model in draft.discovered_models" :key="model" :value="model" /></datalist>
                </Field>
                <Field label="Secret env reference" hint="only the variable name is stored">
                  <input class="mono" v-model.trim="draft.secret_ref" :placeholder="draft.provider_type === 'local' ? 'ANALYSIS_PROVIDER_OPEN_WEBUI_KEY' : draft.provider_type === 'openai' ? 'ANALYSIS_PROVIDER_OPENAI_KEY' : 'MCP_PROVIDER_NEWS_TOKEN'" />
                </Field>
                <Field label="Timeout (s)"><input class="mono" v-model.number="draft.timeout_sec" type="number" min="1" max="120" step="1" /></Field>
              </div>

              <Toggle
                v-if="draft.provider_type === 'local' || draft.provider_type === 'openai'"
                :label="`Enable ${draft.provider_type === 'local' ? 'Open WebUI' : 'OpenAI'} web search`"
                sub="Search remains advisory and must not be used as an execution price feed."
                :checked="draft.web_search_enabled"
                @change="draft.web_search_enabled = $event"
              />

              <hr class="hr" />
              <div>
                <div class="section-label">Assigned capabilities</div>
                <div class="chips">
                  <span v-for="capability in metadata.capabilities" :key="capability" class="chip" :data-on="draft.capabilities.includes(capability)" @click="toggleCapability(capability)">{{ capabilityLabels[capability] }}</span>
                </div>
              </div>

              <div v-if="draft.provider_type === 'mcp' && draft.capabilities.length">
                <div class="section-label">Capability → tool mapping</div>
                <div class="mapping-grid">
                  <Field v-for="capability in draft.capabilities" :key="capability" :label="capabilityLabels[capability]">
                    <select :value="mappedTool(capability)" @change="updateMappedTool(capability, $event)">
                      <option value="">Select allowed tool</option>
                      <option v-for="tool in draft.allowed_tools" :key="tool" :value="tool">{{ tool }}</option>
                    </select>
                  </Field>
                </div>
              </div>

              <div v-if="draft.provider_type === 'mcp' || draft.provider_type === 'local'">
                <div class="section-label">{{ draft.provider_type === "local" ? "Open WebUI tool IDs · deny-by-default" : "Discovered tools · allowlist (deny-by-default)" }}</div>
                <div v-if="draft.discovered_tools.length" class="stack-sm">
                  <label v-for="tool in draft.discovered_tools" :key="tool.name" class="tool-row">
                    <input type="checkbox" :checked="draft.allowed_tools.includes(tool.name)" @change="toggleTool(tool.name)" />
                    <span><strong class="mono">{{ tool.name }}</strong><small class="faint" style="display: block">{{ tool.description || "No description provided" }}</small></span>
                  </label>
                </div>
                <Field v-else-if="draft.provider_type === 'local'" hint="Use IDs configured in Open WebUI. Leave empty to deny all explicit tools.">
                  <textarea class="code" :value="draft.allowed_tools.join('\n')" rows="4" placeholder="server:mcp:trusted-search" @input="updateAllowedTools" />
                </Field>
                <p v-else class="muted" style="font-size: var(--text-sm); margin: 0">Save and test the MCP provider to discover tools.</p>
              </div>

              <div v-if="draft.id" style="background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--sp-5)">
                <Kv k="Health"><Badge :tone="badgeClass(draft.health === 'HEALTHY' ? 'OK' : draft.health)">{{ draft.health }}</Badge></Kv>
                <Kv k="Latency" :v="draft.latency_ms == null ? '—' : `${draft.latency_ms} ms`" mono />
                <Kv v-if="draft.last_error" k="Last error"><span class="neg" style="font-weight: 400; overflow-wrap: anywhere">{{ draft.last_error }}</span></Kv>
              </div>

              <div class="row" style="gap: var(--sp-4)">
                <Btn v-if="draft.id" variant="danger" icon="x" :disabled="deleting || saving || testing" @click="removeProvider">Delete</Btn>
                <span style="flex: 1" />
                <Btn variant="secondary" icon="link" :loading="testing" :disabled="!draft.id || testing || saving" @click="testConnection">Test connection</Btn>
                <Btn icon="save" :loading="saving" :disabled="saving || testing" @click="save">Save provider</Btn>
              </div>
              <span v-if="!draft.id" class="hint">Save before running connection test and tool discovery.</span>
            </div>
          </Panel>

          <Panel v-if="routing" title="Active capability routing">
            <template #action><span class="faint" style="font-size: var(--text-xs)">enabled + healthy only</span></template>
            <div>
              <div v-for="capability in metadata.capabilities" :key="capability" class="route-row">
                <span class="mono" style="font-size: var(--text-sm)">{{ capability }}</span>
                <span v-if="routing[capability]?.length" class="chain">
                  <template v-for="(provider, index) in routing[capability]" :key="provider.id">
                    <span v-if="index > 0" class="arr"><Icon name="caret" :size="12" /></span>
                    <span class="node" :class="{ first: index === 0 }">{{ provider.display_name }}</span>
                  </template>
                </span>
                <Badge v-else tone="block">NO PROVIDER</Badge>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mapping-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sp-5); }
.tool-row { display: flex; align-items: flex-start; gap: var(--sp-4); padding: var(--sp-4); background: var(--surface-2); border-radius: var(--r-md); cursor: pointer; }
.tool-row input { width: auto; flex: 0 0 auto; margin-top: 3px; }
@media (max-width: 620px) { .mapping-grid { grid-template-columns: 1fr; } }
</style>
