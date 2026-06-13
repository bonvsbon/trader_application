<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { api } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Kv from "../components/ui/Kv.vue";
import Reasons from "../components/ui/Reasons.vue";
import Notice from "../components/ui/Notice.vue";
import VerdictHero from "../components/ui/VerdictHero.vue";
import Icon from "../components/ui/Icon.vue";
import NewsEventList from "../components/NewsEventList.vue";
import { badgeClass } from "../components/ui/badge";

const r = ref<any>(null);
const loading = ref(true);
const error = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    r.value = await api.riskStatus();
    error.value = null;
  } catch (e: any) {
    error.value = e?.message ?? "Failed to load risk status";
  } finally {
    loading.value = false;
  }
}

const problems = computed(() => [
  ...(r.value?.facts.config_problems || []),
  ...(r.value?.facts.data_problems || []),
]);

function newsLabel() {
  const f = r.value.facts;
  if (!f.news_is_live) return { text: "Unavailable", tone: "block" as const };
  return f.news_high_impact ? { text: "Near", tone: "warn" as const } : { text: "Clear", tone: "allow" as const };
}
function volLabel() {
  const f = r.value.facts;
  if (!f.volatility_is_live) return { text: "Unavailable", tone: "block" as const };
  return f.abnormal_volatility ? { text: "Abnormal", tone: "block" as const } : { text: "Normal", tone: "allow" as const };
}

onMounted(load);
</script>

<template>
  <div class="stack">
    <PageHead title="Risk Monitor" sub="Live verdict on a probe XAUUSD order and the facts behind it">
      <template #actions><Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Re-check</Btn></template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>

    <div v-else-if="loading && !r" class="panel panel-pad"><div class="sk-line" style="width: 25%" /><div class="sk-line" style="width: 50%; height: 20px; margin-top: 10px" /></div>

    <template v-else-if="r">
      <VerdictHero :verdict="r.decision" headline="Current verdict" :reasons="r.reasons" :warnings="r.warnings" symbol="XAUUSD" />

      <div class="risk-grid">
        <Panel title="Current facts">
          <Kv k="Bridge"><Badge :tone="badgeClass(r.facts.bridge_health)">{{ r.facts.bridge_health }}</Badge></Kv>
          <Kv k="Account"><Badge :tone="badgeClass(r.facts.account_type)">{{ r.facts.account_type }}</Badge></Kv>
          <Kv k="Spread (pts)" mono><span class="neg">{{ r.facts.spread_points ?? "—" }}</span></Kv>
          <Kv k="Free margin %" :v="`${r.facts.free_margin_pct}%`" mono />
          <Kv k="Open positions" :v="r.facts.open_positions" mono />
          <Kv k="Trades today" :v="r.facts.trades_today" mono />
          <Kv k="High-impact news"><Badge :tone="newsLabel().tone">{{ newsLabel().text }}</Badge></Kv>
          <Kv k="Volatility feed"><Badge :tone="volLabel().tone">{{ volLabel().text }}</Badge></Kv>
        </Panel>

        <Panel title="Configured limits">
          <Kv k="Max risk / trade" :v="`${r.limits.max_risk_per_trade_pct}%`" mono />
          <Kv k="Max open positions" :v="r.limits.max_open_positions" mono />
          <Kv k="Max trades / day" :v="r.limits.max_trades_per_day" mono />
          <Kv k="Max spread" :v="`${r.limits.max_spread_points} pts`" mono />
          <Kv k="Max order volume" :v="`${r.limits.max_order_volume_lots} lots`" mono />
          <Kv k="Daily max loss" :v="`${r.limits.daily_max_loss_pct}%`" mono />
        </Panel>
      </div>

      <Panel title="Upcoming high-impact USD events">
        <template #action>
          <Badge :tone="newsLabel().tone">{{ newsLabel().text }}</Badge>
        </template>
        <NewsEventList
          :events="r.facts.news_events || []"
          :empty-text="r.facts.news_is_live ? 'ไม่พบข่าว USD แรงที่กำลังจะมาถึงในปฏิทินปัจจุบัน' : r.facts.news_summary"
        />
      </Panel>

      <Panel title="Safety problems">
        <Reasons v-if="problems.length" :items="problems" />
        <div v-else class="row" style="color: var(--allow-fg); gap: var(--sp-4)">
          <Icon name="check" :size="16" />
          <span style="font-size: var(--text-sm)">No configuration or data problems detected. All risk inputs are fresh.</span>
        </div>
      </Panel>
    </template>
  </div>
</template>

<style scoped>
.risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-6); }
@media (max-width: 720px) { .risk-grid { grid-template-columns: 1fr; } }
</style>
