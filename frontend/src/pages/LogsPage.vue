<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { api } from "../api/client";

type Tab = "audit" | "risk" | "system";
const tab = ref<Tab>("audit");
const audit = ref<any[]>([]);
const risk = ref<any[]>([]);
const system = ref<any[]>([]);
const loading = ref(true);

const tabs: { id: Tab; label: string }[] = [
  { id: "audit", label: "Audit trail" },
  { id: "risk", label: "Risk decisions" },
  { id: "system", label: "System" },
];

function fmt(ts: string | null) {
  return ts ? new Date(ts).toLocaleString() : "—";
}

async function load() {
  loading.value = true;
  try {
    [audit.value, risk.value, system.value] = await Promise.all([api.audit(), api.riskLogs(), api.logs()]);
  } catch { /* backend down */ }
  finally { loading.value = false; }
}
onMounted(load);

const current = computed(() => (tab.value === "audit" ? audit.value : tab.value === "risk" ? risk.value : system.value));
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Logs</h2>
      <p class="sub">Append-only audit trail, risk decisions, and system events.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div class="row" style="gap: var(--sp-3); margin-bottom: var(--sp-6)">
    <button v-for="t in tabs" :key="t.id" class="btn sm" :class="tab === t.id ? '' : 'ghost'" @click="tab = t.id">{{ t.label }}</button>
  </div>

  <section class="panel pad-tight">
    <div v-if="loading" class="stack" style="padding: var(--sp-4)">
      <div class="skeleton sk-line" v-for="i in 5" :key="i" :style="{ width: 90 - i * 6 + '%' }"></div>
    </div>

    <div v-else-if="!current.length" class="empty">
      <div class="icon">▤</div>
      <div class="title">Nothing logged yet</div>
      <p class="muted">Submit an order from the Manual Order page to populate the trail.</p>
    </div>

    <div v-else class="table-wrap">
      <table v-if="tab === 'audit'">
        <thead><tr><th>Time</th><th>Event</th><th>Symbol</th><th>Decision</th><th>Account</th><th>Approval</th></tr></thead>
        <tbody>
          <tr v-for="a in audit" :key="a.id">
            <td class="muted mono">{{ fmt(a.created_at) }}</td>
            <td class="mono">{{ a.event }}</td>
            <td>{{ a.symbol ?? "—" }}</td>
            <td><span v-if="a.decision" class="badge" :class="a.decision">{{ a.decision }}</span><span v-else class="muted">—</span></td>
            <td>{{ a.account_type ?? "—" }}</td>
            <td>{{ a.user_approval === null ? "—" : (a.user_approval ? "Yes" : "No") }}</td>
          </tr>
        </tbody>
      </table>

      <table v-else-if="tab === 'risk'">
        <thead><tr><th>Time</th><th>Symbol</th><th>Decision</th><th>Reasons</th></tr></thead>
        <tbody>
          <tr v-for="x in risk" :key="x.id">
            <td class="muted mono">{{ fmt(x.created_at) }}</td>
            <td>{{ x.symbol }}</td>
            <td><span class="badge" :class="x.decision">{{ x.decision }}</span></td>
            <td class="muted">{{ [...(x.reasons || []), ...(x.warnings || [])].join("; ") || "—" }}</td>
          </tr>
        </tbody>
      </table>

      <table v-else>
        <thead><tr><th>Time</th><th>Level</th><th>Source</th><th>Message</th></tr></thead>
        <tbody>
          <tr v-for="l in system" :key="l.id">
            <td class="muted mono">{{ fmt(l.created_at) }}</td>
            <td><span class="badge no-dot" :class="l.level === 'ERROR' ? 'BLOCK' : l.level === 'WARNING' ? 'WARN' : ''">{{ l.level }}</span></td>
            <td class="mono">{{ l.source }}</td>
            <td>{{ l.message }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
