<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { api } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Tabs from "../components/ui/Tabs.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { badgeClass } from "../components/ui/badge";

type Tab = "audit" | "risk" | "system";
const tab = ref<Tab>("audit");
const audit = ref<any[]>([]);
const risk = ref<any[]>([]);
const system = ref<any[]>([]);
const loading = ref(true);

const tabs = computed(() => [
  { id: "audit", label: "Audit trail", count: audit.value.length },
  { id: "risk", label: "Risk decisions", count: risk.value.length },
  { id: "system", label: "System", count: system.value.length },
]);

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
  <div class="stack">
    <PageHead title="Logs" sub="Append-only audit trail · risk decisions · system events">
      <template #actions><Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn></template>
    </PageHead>

    <Tabs :tabs="tabs" :active="tab" @change="tab = $event as Tab" />

    <Panel :pad="false">
      <div v-if="loading && !current.length" class="stack" style="padding: var(--sp-6)">
        <div class="sk-line" v-for="i in 5" :key="i" :style="{ width: 90 - i * 6 + '%' }" />
      </div>
      <EmptyState v-else-if="!current.length" icon="logs" title="Nothing logged yet" desc="Submit an order from the Manual Order page to populate the trail." />
      <div v-else class="table-wrap" style="padding: var(--sp-3)">
        <table v-if="tab === 'audit'" class="tbl">
          <thead><tr><th>Time</th><th>Event</th><th>Symbol</th><th>Decision</th><th>Account</th><th>Approval</th></tr></thead>
          <tbody>
            <tr v-for="a in audit" :key="a.id" class="hoverable">
              <td class="muted mono">{{ fmt(a.created_at) }}</td>
              <td class="mono">{{ a.event }}</td>
              <td>{{ a.symbol ?? "—" }}</td>
              <td><Badge v-if="a.decision" :tone="badgeClass(a.decision)">{{ a.decision }}</Badge><span v-else class="faint">—</span></td>
              <td><Badge v-if="a.account_type" :tone="badgeClass(a.account_type)" no-dot>{{ a.account_type }}</Badge><span v-else class="faint">—</span></td>
              <td class="muted">{{ a.user_approval === null ? "—" : (a.user_approval ? "Yes" : "No") }}</td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="tab === 'risk'" class="tbl">
          <thead><tr><th>Time</th><th>Symbol</th><th>Decision</th><th>Reasons</th></tr></thead>
          <tbody>
            <tr v-for="x in risk" :key="x.id" class="hoverable">
              <td class="muted mono">{{ fmt(x.created_at) }}</td>
              <td>{{ x.symbol }}</td>
              <td><Badge :tone="badgeClass(x.decision)">{{ x.decision }}</Badge></td>
              <td class="mono muted">{{ [...(x.reasons || []), ...(x.warnings || [])].join("; ") || "—" }}</td>
            </tr>
          </tbody>
        </table>

        <table v-else class="tbl">
          <thead><tr><th>Time</th><th>Level</th><th>Source</th><th>Message</th></tr></thead>
          <tbody>
            <tr v-for="l in system" :key="l.id" class="hoverable">
              <td class="muted mono">{{ fmt(l.created_at) }}</td>
              <td><span class="lvl" :class="l.level.toLowerCase()">{{ l.level }}</span></td>
              <td class="mono muted">{{ l.source }}</td>
              <td>{{ l.message }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  </div>
</template>
