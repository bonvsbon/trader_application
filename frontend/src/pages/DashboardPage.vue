<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { api } from "../api/client";
import RealtimeWatchlist from "../components/RealtimeWatchlist.vue";

const d = ref<any>(null);
const loading = ref(true);
const error = ref<string | null>(null);
let retryTimer: number | undefined;

async function load() {
  loading.value = true;
  try {
    d.value = await api.dashboard();
    error.value = null;
  } catch (e: any) {
    error.value = e?.message ?? "Failed to load dashboard";
  } finally {
    loading.value = false;
  }
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
  <div class="page-head">
    <h2>Dashboard</h2>
    <p class="sub">Account, risk, and workflow at a glance.</p>
  </div>

  <div v-if="error" class="notice">
    <span>{{ error }}. Backend did not respond on port 8000.</span>
    <button class="btn secondary sm retry" @click="load" :disabled="loading">
      Retry
    </button>
  </div>

  <template v-else-if="loading">
    <div class="panel" style="margin-bottom: var(--sp-6)">
      <div class="skeleton sk-line" style="width: 30%"></div>
      <div class="skeleton sk-line" style="width: 60%; height: 22px"></div>
    </div>
    <div class="grid">
      <div class="panel" v-for="i in 4" :key="i">
        <div class="skeleton sk-line" style="width: 40%"></div>
        <div class="skeleton sk-line" style="width: 80%"></div>
        <div class="skeleton sk-line" style="width: 65%"></div>
      </div>
    </div>
  </template>

  <template v-else-if="d">
    <!-- Safety-first: the risk verdict leads the page. -->
    <section class="panel risk-hero" :data-decision="d.risk.decision">
      <div class="panel-head">
        <span class="panel-title">Trade readiness</span>
        <span class="badge lg" :class="d.risk.decision">{{ d.risk.decision }}</span>
      </div>
      <p v-if="d.risk.decision === 'ALLOW'" class="muted">
        All risk checks pass for {{ d.account.account_type }} trading in {{ d.trading_mode }} mode.
      </p>
      <ul v-if="d.risk.reasons.length" class="reasons">
        <li v-for="(r, i) in d.risk.reasons" :key="i">{{ r }}</li>
      </ul>
      <ul v-if="d.risk.warnings.length" class="reasons warn">
        <li v-for="(w, i) in d.risk.warnings" :key="i">{{ w }}</li>
      </ul>
    </section>

    <div class="grid" style="margin-top: var(--sp-6)">
      <section class="panel">
        <div class="panel-head"><span class="panel-title">Connection</span></div>
        <div class="kv"><span class="label">Bridge</span><span class="value"><span class="badge" :class="d.bridge_health">{{ d.bridge_health }}</span></span></div>
        <div class="kv"><span class="label">Account</span><span class="value"><span class="badge" :class="d.account.account_type">{{ d.account.account_type }}</span></span></div>
        <div class="kv"><span class="label">Mode</span><span class="value mono">{{ d.trading_mode }}</span></div>
      </section>

      <section class="panel">
        <div class="panel-head"><span class="panel-title">Account</span></div>
        <div class="kv"><span class="label">Balance</span><span class="value mono">{{ d.account.balance.toLocaleString() }}</span></div>
        <div class="kv"><span class="label">Equity</span><span class="value mono">{{ d.account.equity.toLocaleString() }}</span></div>
        <div class="kv"><span class="label">Free margin</span><span class="value mono">{{ d.account.free_margin_pct }}%</span></div>
      </section>

      <section class="panel" v-if="d.quote">
        <div class="panel-head"><span class="panel-title">{{ d.quote.symbol }}</span></div>
        <div class="kv"><span class="label">Bid</span><span class="value mono">{{ d.quote.bid }}</span></div>
        <div class="kv"><span class="label">Ask</span><span class="value mono">{{ d.quote.ask }}</span></div>
        <div class="kv"><span class="label">Spread</span><span class="value mono">{{ d.quote.spread_points }} pts</span></div>
      </section>

      <section class="panel">
        <div class="panel-head"><span class="panel-title">Activity</span></div>
        <div class="kv"><span class="label">Open positions</span><span class="value mono">{{ d.open_positions }}</span></div>
        <div class="kv"><span class="label">Trades today</span><span class="value mono">{{ d.trades_today }}</span></div>
        <div class="kv"><span class="label">High-impact news</span><span class="value"><span class="badge" :class="!d.news.is_live || d.news.high_impact ? 'BLOCK' : 'ALLOW'">{{ !d.news.is_live ? "Unavailable" : d.news.high_impact ? "Near" : "Clear" }}</span></span></div>
        <div class="kv"><span class="label">Volatility feed</span><span class="value"><span class="badge" :class="!d.volatility.is_live || d.volatility.abnormal ? 'BLOCK' : 'ALLOW'">{{ !d.volatility.is_live ? "Unavailable" : d.volatility.abnormal ? "Abnormal" : "Normal" }}</span></span></div>
      </section>
    </div>
    <RealtimeWatchlist />
  </template>
</template>

<style scoped>
.risk-hero { border-color: color-mix(in oklab, var(--accent) 22%, var(--border)); }
.risk-hero[data-decision="BLOCK"] { border-color: color-mix(in oklab, var(--block-fg) 38%, var(--border)); background: color-mix(in oklab, var(--block-bg) 28%, var(--surface)); }
.risk-hero[data-decision="WARN"] { border-color: color-mix(in oklab, var(--warn-fg) 34%, var(--border)); background: color-mix(in oklab, var(--warn-bg) 24%, var(--surface)); }
.notice { align-items: center; justify-content: space-between; margin-bottom: var(--sp-6); }
.retry { flex: 0 0 auto; }
</style>
