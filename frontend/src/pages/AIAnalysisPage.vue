<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  api,
  type AnalysisCapability,
  type AnalysisRunResult,
} from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Field from "../components/ui/Field.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";

const CAPABILITIES: AnalysisCapability[] = [
  "news_search", "economic_calendar", "chart_market",
  "volatility_session", "proposal_explanation", "loss_review",
];

const capability = ref<AnalysisCapability>("chart_market");
const prompt = ref("Summarize the supplied market context and identify risks. Do not place an order.");
const contextText = ref('{\n  "symbol": "XAUUSD"\n}');
const result = ref<AnalysisRunResult | null>(null);
const snapshots = ref<any[]>([]);
const running = ref(false);
const error = ref<string | null>(null);

async function loadSnapshots() {
  snapshots.value = await api.analysisSnapshots();
}

async function run() {
  running.value = true;
  error.value = null;
  result.value = null;
  try {
    const context = JSON.parse(contextText.value);
    result.value = await api.runAnalysis(capability.value, prompt.value, context);
    await loadSnapshots();
  } catch (e: any) {
    error.value = e instanceof SyntaxError
      ? "Context must be valid JSON."
      : e?.response?.data?.detail ?? e?.message ?? "Analysis failed";
  } finally {
    running.value = false;
  }
}

onMounted(() => loadSnapshots().catch(() => undefined));
</script>

<template>
  <div class="stack">
    <PageHead title="AI Analysis" sub="Advisory analysis via provider routing — never places orders">
      <template #actions><Badge tone="accent" no-dot>advisory only</Badge></template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>

    <div class="ai-cols">
      <Panel title="Request">
        <div class="stack">
          <Field label="Capability">
            <div class="chips">
              <span v-for="c in CAPABILITIES" :key="c" class="chip" :data-on="capability === c" @click="capability = c">{{ c }}</span>
            </div>
          </Field>
          <Field label="Prompt"><textarea v-model="prompt" style="min-height: 84px" /></Field>
          <Field label="Context JSON"><textarea v-model="contextText" class="code" style="min-height: 96px" /></Field>
          <Notice tone="neutral">Analysis is advisory and is recorded for provenance. Seed prompts with “Do not place an order.”</Notice>
          <Btn icon="sparkle" :loading="running" :disabled="running" @click="run">Run advisory analysis</Btn>
        </div>
      </Panel>

      <Panel title="Result">
        <EmptyState v-if="!result && !running" icon="sparkle" title="No analysis yet" desc="Pick a capability and run a request to see the advisory result and its provenance." />
        <div v-else-if="running" class="empty">
          <span class="spin" style="width: 26px; height: 26px; border-width: 3px" />
          <div class="et" style="margin-top: 8px">Routing to provider…</div>
          <div class="ed">Resolving {{ capability }} through the capability chain</div>
        </div>
        <div v-else-if="result" class="fade-in stack">
          <div class="row between">
            <Badge :tone="result.available ? 'allow' : 'block'" lg>{{ result.available ? "AVAILABLE" : "NO PROVIDER" }}</Badge>
            <span class="chip" data-on="true">{{ result.capability }}</span>
          </div>
          <p v-if="result.summary" style="margin: 0; line-height: 1.6; font-size: var(--text-base); white-space: pre-wrap">{{ result.summary }}</p>
          <p v-else class="muted" style="margin: 0; font-size: var(--text-sm)">No summary returned by the provider route.</p>
          <hr class="hr" />
          <div class="meta-grid">
            <div><div class="m-k">Provider</div><div class="m-v">{{ result.provider_name ?? "—" }}</div></div>
            <div><div class="m-k">Model / tool</div><div class="m-v mono">{{ result.model_or_tool ?? "—" }}</div></div>
            <div><div class="m-k">Correlation id</div><div class="m-v mono">{{ result.correlation_id }}</div></div>
          </div>
        </div>
      </Panel>
    </div>

    <Panel title="Recent analysis attempts" :pad="false">
      <template #action><Btn sm variant="secondary" icon="refresh" @click="loadSnapshots">Refresh</Btn></template>
      <div v-if="snapshots.length" class="table-wrap" style="padding: var(--sp-3)">
        <table class="tbl">
          <thead><tr><th>Time</th><th>Capability</th><th>Provider</th><th>Model / tool</th><th>Status</th><th>Detail</th></tr></thead>
          <tbody>
            <tr v-for="item in snapshots" :key="item.id" class="hoverable">
              <td class="mono muted">{{ new Date(item.created_at).toLocaleString() }}</td>
              <td>{{ item.capability }}</td>
              <td>{{ item.provider_name ?? "—" }}</td>
              <td class="mono">{{ item.model_or_tool ?? "—" }}</td>
              <td><Badge :tone="item.success ? 'allow' : 'block'">{{ item.success ? "OK" : "FAILED" }}</Badge></td>
              <td class="muted detail">{{ item.success ? item.output_summary : item.error }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else icon="analysis" title="No analysis attempts recorded" desc="Advisory runs and their provenance appear here." />
    </Panel>
  </div>
</template>

<style scoped>
.ai-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-6); align-items: start; }
@media (max-width: 880px) { .ai-cols { grid-template-columns: 1fr; } }
.detail { max-width: 420px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
