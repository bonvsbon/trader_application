<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { api } from "../api/client";
import RealtimeWatchlist from "../components/RealtimeWatchlist.vue";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Kv from "../components/ui/Kv.vue";
import VerdictHero from "../components/ui/VerdictHero.vue";
import AreaChart from "../components/ui/AreaChart.vue";
import Notice from "../components/ui/Notice.vue";
import NewsEventList from "../components/NewsEventList.vue";
import { badgeClass } from "../components/ui/badge";

const d = ref<any>(null);
const daily = ref<any[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
let retryTimer: number | undefined;

async function load() {
  loading.value = true;
  try {
    const [dash, day] = await Promise.all([
      api.dashboard(),
      api.historyDaily().catch(() => []),
    ]);
    d.value = dash;
    daily.value = Array.isArray(day) ? day : [];
    error.value = null;
  } catch (e: any) {
    error.value = e?.message ?? "Failed to load dashboard";
  } finally {
    loading.value = false;
  }
}

// Real cumulative-equity curve: account balance + running realized P&L, oldest → newest.
const equitySeries = computed<number[]>(() => {
  if (!d.value || !daily.value.length) return [];
  const ordered = [...daily.value].reverse();
  const base = d.value.account.balance;
  let acc = 0;
  const pts = ordered.map((row) => {
    acc += row.net_pnl ?? 0;
    return +(base + acc).toFixed(2);
  });
  return [base, ...pts];
});
const equityChange = computed(() => {
  const s = equitySeries.value;
  return s.length ? s[s.length - 1] - s[0] : 0;
});
const equityChangePct = computed(() => {
  const s = equitySeries.value;
  return s.length && s[0] ? (equityChange.value / s[0]) * 100 : 0;
});

function newsLabel() {
  if (!d.value?.news.is_live) return { text: "Unavailable", tone: "block" as const };
  return d.value.news.high_impact
    ? { text: "Near", tone: "warn" as const }
    : { text: "Clear", tone: "allow" as const };
}
function volLabel() {
  if (!d.value?.volatility.is_live) return { text: "Unavailable", tone: "block" as const };
  return d.value.volatility.abnormal
    ? { text: "Abnormal", tone: "block" as const }
    : { text: "Normal", tone: "allow" as const };
}
function money(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

onMounted(() => {
  load();
  retryTimer = window.setInterval(() => {
    if (error.value && !loading.value) load();
  }, 8000);
});
onUnmounted(() => retryTimer && clearInterval(retryTimer));
</script>

<template>
  <div class="stack">
    <PageHead title="Dashboard" sub="Account, risk and workflow at a glance · XAUUSD">
      <template #actions>
        <Badge v-if="d" :tone="badgeClass(d.bridge_health)">Bridge {{ d.bridge_health }}</Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">
      {{ error }}. Backend did not respond.
    </Notice>

    <template v-else-if="loading && !d">
      <div class="panel panel-pad"><div class="sk-line" style="width: 30%" /><div class="sk-line" style="width: 60%; height: 22px; margin-top: 10px" /></div>
      <div class="grid">
        <div class="panel panel-pad" v-for="i in 4" :key="i">
          <div class="sk-line" style="width: 40%" /><div class="sk-line" style="width: 80%; margin-top: 8px" /><div class="sk-line" style="width: 65%; margin-top: 8px" />
        </div>
      </div>
    </template>

    <template v-else-if="d">
      <VerdictHero
        :verdict="d.risk.decision"
        headline="Trade readiness"
        :reasons="d.risk.reasons"
        :warnings="d.risk.warnings"
        symbol="XAUUSD"
      />

      <Panel v-if="equitySeries.length > 1" :pad="false">
        <div class="panel-head">
          <div class="col" style="gap: 2px">
            <span class="panel-title">Equity curve · last {{ daily.length }} sessions</span>
            <span class="faint" style="font-size: var(--text-xs)">Balance + cumulative realized P&amp;L, USD</span>
          </div>
          <div class="row" style="gap: var(--sp-6); align-items: baseline">
            <span class="mono" style="font-size: var(--text-2xl); font-weight: 700; letter-spacing: -0.02em">${{ money(d.account.equity) }}</span>
            <span class="mono" :class="equityChange >= 0 ? 'pos' : 'neg'" style="font-weight: 600; font-size: var(--text-base)">
              {{ equityChange >= 0 ? "▲" : "▼" }} {{ equityChange >= 0 ? "+" : "" }}{{ equityChange.toFixed(2) }} ({{ equityChangePct >= 0 ? "+" : "" }}{{ equityChangePct.toFixed(2) }}%)
            </span>
          </div>
        </div>
        <div style="padding: var(--sp-7) var(--sp-7) var(--sp-6)">
          <AreaChart :data="equitySeries" :height="140" :color="equityChange >= 0 ? 'var(--pos)' : 'var(--neg)'" :axis-labels="[`${daily.length} sessions ago`, '', 'today']" />
        </div>
        <div class="eq-strip" style="display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--border)">
          <div v-for="(cell, i) in [
            ['Balance', `$${money(d.account.balance)}`],
            ['Free margin', `${d.account.free_margin_pct}%`],
            ['Open positions', `${d.open_positions}`],
            ['Trades today', `${d.trades_today}`],
          ]" :key="cell[0]" class="col" :style="{ gap: '4px', padding: 'var(--sp-6) var(--sp-7)', borderLeft: i ? '1px solid var(--border)' : 'none' }">
            <span class="faint" style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.05em">{{ cell[0] }}</span>
            <span class="mono" style="font-size: var(--text-lg); font-weight: 700">{{ cell[1] }}</span>
          </div>
        </div>
      </Panel>

      <div class="grid">
        <Panel title="Connection">
          <Kv k="Bridge health"><Badge :tone="badgeClass(d.bridge_health)">{{ d.bridge_health }}</Badge></Kv>
          <Kv k="Account type"><Badge :tone="d.account.account_type === 'DEMO' ? 'allow' : 'block'">{{ d.account.account_type }}</Badge></Kv>
          <Kv k="Trading mode"><Badge tone="accent" no-dot>{{ d.trading_mode }}</Badge></Kv>
        </Panel>
        <Panel title="Account">
          <Kv k="Balance" :v="`$${money(d.account.balance)}`" mono />
          <Kv k="Equity" :v="`$${money(d.account.equity)}`" mono tone="pos" />
          <Kv k="Free margin" :v="`${d.account.free_margin_pct}%`" mono />
        </Panel>
        <Panel v-if="d.quote" :title="`Quote · ${d.quote.symbol}`">
          <Kv k="Bid" :v="d.quote.bid" mono />
          <Kv k="Ask" :v="d.quote.ask" mono />
          <Kv k="Spread" :v="`${d.quote.spread_points} pts`" mono tone="neg" />
          <div class="faint" style="font-size: var(--text-xs); margin-top: var(--sp-4)">Broker quote · drives risk &amp; execution</div>
        </Panel>
        <Panel title="Activity">
          <Kv k="Open positions" :v="d.open_positions" mono />
          <Kv k="Trades today" :v="d.trades_today" mono />
          <Kv k="High-impact news"><Badge :tone="newsLabel().tone">{{ newsLabel().text }}</Badge></Kv>
          <Kv k="Volatility feed"><Badge :tone="volLabel().tone" no-dot>{{ volLabel().text }}</Badge></Kv>
        </Panel>
      </div>

      <Panel title="Upcoming high-impact USD events">
        <template #action>
          <Badge :tone="newsLabel().tone">{{ newsLabel().text }}</Badge>
        </template>
        <NewsEventList
          :events="d.news.events || []"
          :empty-text="d.news.is_live ? 'ไม่พบข่าว USD แรงที่กำลังจะมาถึงในปฏิทินปัจจุบัน' : d.news.summary"
        />
      </Panel>

      <RealtimeWatchlist />
    </template>
  </div>
</template>
