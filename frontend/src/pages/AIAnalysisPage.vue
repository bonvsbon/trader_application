<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  api,
  type AnalysisCapability,
  type AnalysisRunResult,
} from "../api/client";

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
  <div class="page-head">
    <h2>AI Analysis</h2>
    <p class="sub">Run advisory analysis through the enabled provider route and inspect provenance.</p>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>

  <div class="analysis-grid">
    <section class="panel">
      <div class="field">
        <label>Capability</label>
        <select v-model="capability">
          <option value="news_search">News search</option>
          <option value="economic_calendar">Economic calendar</option>
          <option value="chart_market">Chart / market</option>
          <option value="volatility_session">Volatility / session</option>
          <option value="proposal_explanation">Proposal explanation</option>
          <option value="loss_review">Loss review</option>
        </select>
      </div>
      <div class="field">
        <label>Prompt</label>
        <textarea v-model="prompt" rows="5"></textarea>
      </div>
      <div class="field">
        <label>Context JSON</label>
        <textarea v-model="contextText" rows="10" class="mono"></textarea>
      </div>
      <button class="btn full" @click="run" :disabled="running">
        <span v-if="running" class="spin"></span>
        Run advisory analysis
      </button>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">Result</span>
        <span v-if="result" class="badge" :class="result.available ? 'ALLOW' : 'UNKNOWN'">
          {{ result.available ? "AVAILABLE" : "NO PROVIDER" }}
        </span>
      </div>
      <p v-if="result?.summary" class="result-copy">{{ result.summary }}</p>
      <p v-else class="muted">Run an analysis to see the provider response.</p>
      <div v-if="result" class="meta">
        <div class="kv"><span class="label">Provider</span><span class="value">{{ result.provider_name ?? "—" }}</span></div>
        <div class="kv"><span class="label">Model / tool</span><span class="value mono">{{ result.model_or_tool ?? "—" }}</span></div>
        <div class="kv"><span class="label">Correlation</span><span class="value mono">{{ result.correlation_id }}</span></div>
      </div>
    </section>
  </div>

  <section class="panel snapshots">
    <div class="panel-head">
      <span class="panel-title">Recent Analysis Attempts</span>
      <button class="btn secondary sm" @click="loadSnapshots">Refresh</button>
    </div>
    <div v-if="snapshots.length" class="table-wrap">
      <table>
        <thead><tr><th>Time</th><th>Capability</th><th>Provider</th><th>Model / tool</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>
          <tr v-for="item in snapshots" :key="item.id">
            <td class="mono muted">{{ new Date(item.created_at).toLocaleString() }}</td>
            <td>{{ item.capability }}</td>
            <td>{{ item.provider_name ?? "—" }}</td>
            <td class="mono">{{ item.model_or_tool ?? "—" }}</td>
            <td><span class="badge" :class="item.success ? 'ALLOW' : 'BLOCK'">{{ item.success ? "OK" : "FAILED" }}</span></td>
            <td class="detail">{{ item.success ? item.output_summary : item.error }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="muted">No analysis attempts recorded.</p>
  </section>
</template>

<style scoped>
.notice { margin-bottom: var(--sp-5); }
.analysis-grid { display: grid; grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.1fr); gap: var(--sp-6); }
.result-copy { white-space: pre-wrap; line-height: 1.65; }
.meta { margin-top: var(--sp-6); padding-top: var(--sp-5); border-top: 1px solid var(--border); }
.snapshots { margin-top: var(--sp-6); }
.detail { max-width: 420px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
@media (max-width: 900px) {
  .analysis-grid { grid-template-columns: 1fr; }
}
</style>
