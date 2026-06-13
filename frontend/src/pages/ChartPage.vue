<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { api, type Candle } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Field from "../components/ui/Field.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import CandlestickChart, { type ChartMarker } from "../components/ui/CandlestickChart.vue";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];

const symbol = ref("XAUUSD");
const timeframe = ref("H1");
const count = ref(200);
const showChannels = ref(true);
const showMarkers = ref(true);
const autoRefresh = ref(true);

const candles = ref<Candle[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const d40 = ref<number | null>(40);
const d20 = ref<number | null>(20);
const proposals = ref<any[]>([]);
const livePrice = ref<number | null>(null);
const liveQuoteTime = ref<number | null>(null);
const liveSource = ref<string | null>(null);

let refreshTimer: number | undefined;
let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;

const lastClose = computed(() => (candles.value.length ? candles.value[candles.value.length - 1].close : null));
const priceNow = computed(() => livePrice.value ?? lastClose.value);
const quoteIsFresh = computed(
  () => liveQuoteTime.value != null && Date.now() - liveQuoteTime.value < 60_000,
);
const change = computed(() => {
  if (candles.value.length < 2 || priceNow.value == null) return { abs: 0, pct: 0 };
  const first = candles.value[0].open;
  const abs = priceNow.value - first;
  return { abs, pct: first ? (abs / first) * 100 : 0 };
});

// Entry/SL/TP markers from the latest still-relevant proposal for this symbol.
const markers = computed<ChartMarker[]>(() => {
  if (!showMarkers.value) return [];
  const active = proposals.value
    .filter((p) => p.symbol === symbol.value && !["REJECTED", "CANCELLED", "EXPIRED"].includes(p.status))
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
  if (!active) return [];
  return [
    { price: active.entry_price, label: `${active.side} entry`, tone: active.side === "BUY" ? "pos" : "neg" },
    { price: active.sl, label: "SL", tone: "neg" },
    { price: active.tp, label: "TP", tone: "pos" },
  ];
});

async function loadCandles() {
  loading.value = true;
  try {
    const res = await api.marketCandles(symbol.value.toUpperCase(), timeframe.value, count.value);
    candles.value = res.candles;
    error.value = res.error ?? (res.candles.length ? null : "No candle data returned for this symbol.");
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Failed to load candles";
    candles.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadMeta() {
  try {
    const cfg = await api.strategyConfiguration();
    d40.value = cfg.d40_value;
    d20.value = cfg.d20_value;
  } catch { /* keep defaults */ }
  try {
    proposals.value = await api.proposals();
  } catch { /* none */ }
}

function connectLive() {
  socket?.close();
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/market?symbols=${encodeURIComponent(symbol.value.toUpperCase())}`);
  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    const q = (payload.quotes || []).find((x: any) => x.symbol === symbol.value.toUpperCase());
    if (q) {
      livePrice.value = (q.bid + q.ask) / 2;
      liveQuoteTime.value = Date.parse(q.time);
      liveSource.value = payload.source ?? null;
    }
  };
  socket.onclose = () => { reconnectTimer = window.setTimeout(connectLive, 3000); };
  socket.onerror = () => socket?.close();
}

function setTimeframe(tf: string) {
  timeframe.value = tf;
  loadCandles();
}
function applySymbol() {
  livePrice.value = null;
  liveQuoteTime.value = null;
  loadCandles();
  connectLive();
}

watch(autoRefresh, (on) => {
  if (on) startRefresh();
  else if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = undefined; }
});
function startRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = window.setInterval(() => { if (autoRefresh.value) loadCandles(); }, 20000);
}

function money(n: number | null) {
  return n == null ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

onMounted(() => {
  loadMeta();
  loadCandles();
  connectLive();
  startRefresh();
});
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  socket?.close();
});
</script>

<template>
  <div class="stack">
    <PageHead title="Chart" sub="Realtime OHLC · Donchian D40/D20 · proposal markers">
      <template #actions>
        <Badge :tone="quoteIsFresh ? 'allow' : 'warn'">
          {{ quoteIsFresh ? "LIVE" : livePrice != null ? "STALE / MARKET CLOSED" : "no live tick" }}
        </Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="loadCandles">Refresh</Btn>
      </template>
    </PageHead>

    <Panel :pad="false">
      <div class="chart-controls">
        <Field label="Symbol">
          <input class="mono" v-model="symbol" style="width: 130px" @keyup.enter="applySymbol" />
        </Field>
        <Field label="Timeframe">
          <div class="chips">
            <span v-for="tf in TIMEFRAMES" :key="tf" class="chip" :data-on="timeframe === tf" @click="setTimeframe(tf)">{{ tf }}</span>
          </div>
        </Field>
        <Field label="Candles">
          <input class="mono" type="number" min="10" max="1000" step="10" v-model.number="count" style="width: 90px" @change="loadCandles" />
        </Field>
        <div class="ctrl-toggles">
          <label class="ctrl-check"><input type="checkbox" v-model="showChannels" /> D40/D20</label>
          <label class="ctrl-check"><input type="checkbox" v-model="showMarkers" /> Proposal markers</label>
          <label class="ctrl-check"><input type="checkbox" v-model="autoRefresh" /> Auto-refresh</label>
          <Btn sm variant="secondary" @click="applySymbol">Apply</Btn>
        </div>
      </div>

      <div class="chart-price">
        <span class="mono price-now">${{ money(priceNow) }}</span>
        <span class="mono" :class="change.abs >= 0 ? 'pos' : 'neg'" style="font-weight: 600">
          {{ change.abs >= 0 ? "▲" : "▼" }} {{ change.abs >= 0 ? "+" : "" }}{{ change.abs.toFixed(2) }} ({{ change.pct >= 0 ? "+" : "" }}{{ change.pct.toFixed(2) }}%)
        </span>
        <span class="faint" style="font-size: var(--text-xs)">
          {{ symbol.toUpperCase() }} · {{ timeframe }} · {{ candles.length }} bars<span v-if="liveSource"> · {{ liveSource }}</span>
        </span>
      </div>

      <div style="padding: 0 var(--sp-7) var(--sp-6)">
        <Notice v-if="error" tone="warn">{{ error }}</Notice>
        <div v-if="loading && !candles.length" class="sk-line" style="height: 360px; border-radius: var(--r-md)" />
        <EmptyState v-else-if="!candles.length && !error" icon="market" title="No candles" desc="Adjust the symbol or timeframe." />
        <CandlestickChart
          v-else-if="candles.length"
          :candles="candles"
          :height="380"
          :d40="d40"
          :d20="d20"
          :show-channels="showChannels"
          :markers="markers"
          :live-price="livePrice"
        />
      </div>

      <div class="chart-legend">
        <span class="lg"><i class="sw" style="background: var(--pos)" /> Up bar</span>
        <span class="lg"><i class="sw" style="background: var(--neg)" /> Down bar</span>
        <span class="lg"><i class="ln accent" /> Donchian D{{ d40 }} (entry)</span>
        <span class="lg"><i class="ln faint" /> Donchian D{{ d20 }} (exit)</span>
        <span class="lg"><i class="ln live" /> Live mid price</span>
        <span class="faint" style="margin-left: auto; font-size: var(--text-xs)">Display only — risk &amp; execution use the MT5 broker quote.</span>
      </div>
    </Panel>
  </div>
</template>

<style scoped>
.chart-controls {
  display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--sp-5);
  padding: var(--sp-6) var(--sp-7);
}
.ctrl-toggles { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-5); margin-left: auto; }
.ctrl-check { display: flex; align-items: center; gap: var(--sp-3); font-size: var(--text-sm); color: var(--ink-muted); cursor: pointer; }
.ctrl-check input { width: auto; }
.chart-price {
  display: flex; align-items: baseline; gap: var(--sp-6); flex-wrap: wrap;
  padding: 0 var(--sp-7) var(--sp-5); border-bottom: 1px solid var(--border);
}
.price-now { font-size: var(--text-2xl); font-weight: 700; letter-spacing: -0.02em; }
.chart-legend {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-6);
  padding: var(--sp-5) var(--sp-7); border-top: 1px solid var(--border);
  font-size: var(--text-sm); color: var(--ink-muted);
}
.chart-legend .lg { display: inline-flex; align-items: center; gap: var(--sp-3); }
.chart-legend .sw { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
.chart-legend .ln { width: 16px; height: 0; border-top: 2px solid; display: inline-block; }
.chart-legend .ln.accent { border-top-style: dashed; color: var(--accent); }
.chart-legend .ln.faint { color: var(--ink-faint); }
.chart-legend .ln.live { color: var(--accent-ink); }
</style>
