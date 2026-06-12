<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "../api/client";

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
onMounted(load);
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Risk Monitor</h2>
      <p class="sub">Live verdict for a probe XAUUSD order, with the facts behind it.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>

  <template v-else-if="loading">
    <div class="panel"><div class="skeleton sk-line" style="width: 25%"></div><div class="skeleton sk-line" style="width: 50%; height: 20px"></div></div>
  </template>

  <template v-else-if="r">
    <section class="panel risk-hero" :data-decision="r.decision">
      <div class="panel-head">
        <span class="panel-title">Current verdict</span>
        <span class="badge lg" :class="r.decision">{{ r.decision }}</span>
      </div>
      <p v-if="r.decision === 'ALLOW'" class="muted">No blocking conditions. Trading is permitted under current limits.</p>
      <ul v-if="r.reasons.length" class="reasons"><li v-for="(x, i) in r.reasons" :key="i">{{ x }}</li></ul>
      <ul v-if="r.warnings.length" class="reasons warn"><li v-for="(x, i) in r.warnings" :key="i">{{ x }}</li></ul>
    </section>

    <div class="grid" style="margin-top: var(--sp-6)">
      <section class="panel">
        <div class="panel-head"><span class="panel-title">Current facts</span></div>
        <div class="kv"><span class="label">Bridge</span><span class="value"><span class="badge" :class="r.facts.bridge_health">{{ r.facts.bridge_health }}</span></span></div>
        <div class="kv"><span class="label">Account</span><span class="value"><span class="badge" :class="r.facts.account_type">{{ r.facts.account_type }}</span></span></div>
        <div class="kv"><span class="label">Spread</span><span class="value mono">{{ r.facts.spread_points ?? "—" }} pts</span></div>
        <div class="kv"><span class="label">Free margin</span><span class="value mono">{{ r.facts.free_margin_pct }}%</span></div>
        <div class="kv"><span class="label">Open positions</span><span class="value mono">{{ r.facts.open_positions }}</span></div>
        <div class="kv"><span class="label">Trades today</span><span class="value mono">{{ r.facts.trades_today }}</span></div>
        <div class="kv"><span class="label">High-impact news</span><span class="value"><span class="badge" :class="!r.facts.news_is_live || r.facts.news_high_impact ? 'BLOCK' : 'ALLOW'">{{ !r.facts.news_is_live ? "Unavailable" : r.facts.news_high_impact ? "Near" : "Clear" }}</span></span></div>
        <div class="kv"><span class="label">Volatility feed</span><span class="value"><span class="badge" :class="!r.facts.volatility_is_live || r.facts.abnormal_volatility ? 'BLOCK' : 'ALLOW'">{{ !r.facts.volatility_is_live ? "Unavailable" : r.facts.abnormal_volatility ? "Abnormal" : "Normal" }}</span></span></div>
      </section>

      <section class="panel">
        <div class="panel-head"><span class="panel-title">Configured limits</span></div>
        <div class="kv"><span class="label">Max risk / trade</span><span class="value mono">{{ r.limits.max_risk_per_trade_pct }}%</span></div>
        <div class="kv"><span class="label">Max open positions</span><span class="value mono">{{ r.limits.max_open_positions }}</span></div>
        <div class="kv"><span class="label">Max trades / day</span><span class="value mono">{{ r.limits.max_trades_per_day }}</span></div>
        <div class="kv"><span class="label">Max spread</span><span class="value mono">{{ r.limits.max_spread_points }} pts</span></div>
        <div class="kv"><span class="label">Max order volume</span><span class="value mono">{{ r.limits.max_order_volume_lots }} lots</span></div>
        <div class="kv"><span class="label">Daily max loss</span><span class="value mono">{{ r.limits.daily_max_loss_pct }}%</span></div>
      </section>

      <section class="panel" v-if="r.facts.config_problems?.length || r.facts.data_problems?.length">
        <div class="panel-head"><span class="panel-title" style="color: var(--block-fg)">Safety problems</span></div>
        <ul class="reasons">
          <li v-for="(c, i) in [...(r.facts.config_problems || []), ...(r.facts.data_problems || [])]" :key="i">{{ c }}</li>
        </ul>
      </section>
    </div>
  </template>
</template>

<style scoped>
.risk-hero[data-decision="ALLOW"] { border-color: color-mix(in oklab, var(--allow-fg) 30%, var(--border)); }
.risk-hero[data-decision="BLOCK"] { border-color: color-mix(in oklab, var(--block-fg) 38%, var(--border)); background: color-mix(in oklab, var(--block-bg) 26%, var(--surface)); }
.risk-hero[data-decision="WARN"] { border-color: color-mix(in oklab, var(--warn-fg) 34%, var(--border)); background: color-mix(in oklab, var(--warn-bg) 22%, var(--surface)); }
</style>
