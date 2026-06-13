<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type MarketDataConfiguration } from "../api/client";
import Panel from "./ui/Panel.vue";
import Badge from "./ui/Badge.vue";
import Btn from "./ui/Btn.vue";
import Icon from "./ui/Icon.vue";
import Notice from "./ui/Notice.vue";
import Sparkline from "./ui/Sparkline.vue";

interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  spread_points: number;
  time: string;
  dir?: "up" | "down" | "";
}

interface QuoteError {
  symbol: string;
  error: string;
  code?: string;
  hint?: string;
}

const symbolInput = ref("XAUUSD");
const quotes = ref<Quote[]>([]);
const hist = ref<Record<string, number[]>>({});
const errors = ref<QuoteError[]>([]);
const marketConfig = ref<MarketDataConfiguration | null>(null);
const source = ref("connecting");
const feedStatus = ref("unknown");
const connected = ref(false);
const live = ref(true);
let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;

const providerLabel = computed(() => {
  if (marketConfig.value?.provider === "alpaca") return `Alpaca ${marketConfig.value.feed.toUpperCase()}`;
  if (marketConfig.value?.provider === "mt5") return "MT5 broker";
  return "Market data";
});

const hasBrokerSymbolError = computed(() =>
  errors.value.some((item) => item.code === "broker_symbol_unavailable"),
);

function normalizedSymbols() {
  return Array.from(
    new Set(
      symbolInput.value
        .split(",")
        .map((value) => value.trim().toUpperCase())
        .filter(Boolean),
    ),
  ).slice(0, 25);
}

function connect() {
  socket?.close();
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  if (!live.value) return;
  const symbols = normalizedSymbols();
  if (!symbols.length) return;
  symbolInput.value = symbols.join(", ");
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(
    `${proto}://${location.host}/ws/market?symbols=${encodeURIComponent(symbols.join(","))}`,
  );
  socket.onopen = () => {
    connected.value = true;
  };
  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    source.value = payload.source;
    feedStatus.value = payload.feed_status ?? "unknown";
    const merged = new Map(quotes.value.map((quote) => [quote.symbol, quote]));
    for (const quote of payload.quotes) {
      const prev = merged.get(quote.symbol);
      quote.dir = prev
        ? quote.bid > prev.bid
          ? "up"
          : quote.bid < prev.bid
            ? "down"
            : prev.dir ?? ""
        : "";
      merged.set(quote.symbol, quote);
      const series = hist.value[quote.symbol] ?? [];
      hist.value[quote.symbol] = [...series.slice(-23), quote.bid];
    }
    quotes.value = Array.from(merged.values());
    errors.value = payload.errors;
  };
  socket.onclose = () => {
    connected.value = false;
    if (live.value) reconnectTimer = window.setTimeout(connect, 3000);
  };
  socket.onerror = () => socket?.close();
}

function toggleLive() {
  live.value = !live.value;
  if (live.value) connect();
  else socket?.close();
}

function fmtTime(value: string) {
  return new Date(value).toLocaleTimeString();
}
function trendUp(symbol: string) {
  const s = hist.value[symbol];
  return !s || s[s.length - 1] >= s[0];
}

onMounted(async () => {
  try {
    marketConfig.value = await api.marketDataConfiguration();
  } catch {
    marketConfig.value = null;
  }
  connect();
});
onUnmounted(() => {
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  socket?.close();
});
</script>

<template>
  <Panel :pad="false">
    <div class="panel-head">
      <div class="col" style="gap: 2px">
        <span class="panel-title">Realtime Watchlist</span>
        <span class="faint" style="font-size: var(--text-xs)">
          Display feed: {{ providerLabel }} · execution still uses the MT5 broker quote
        </span>
      </div>
      <div class="row">
        <Badge :tone="connected ? 'allow' : 'warn'">{{ connected ? `${source} · ${feedStatus}` : "RECONNECTING" }}</Badge>
        <Btn sm variant="ghost" :icon="live ? 'square' : 'play'" @click="toggleLive">{{ live ? "Pause" : "Resume" }}</Btn>
      </div>
    </div>

    <div style="padding: var(--sp-5) var(--sp-7)">
      <div class="symbol-control">
        <input v-model="symbolInput" class="mono" aria-label="Watchlist symbols" placeholder="XAUUSD, AAPL, MSFT" @keyup.enter="connect" />
        <Btn sm variant="secondary" @click="connect">Apply</Btn>
      </div>
      <Notice v-if="source === 'mt5:mock'" tone="warn">
        Source <span class="mono">mt5:mock</span> — synthetic test data, not live prices. Order risk &amp; execution always use the real MT5 quote.
      </Notice>
    </div>

    <div class="table-wrap" style="padding: 0 var(--sp-3) var(--sp-3)">
      <table class="tbl">
        <thead>
          <tr><th>Symbol</th><th>Trend</th><th class="num">Bid</th><th class="num">Ask</th><th class="num">Spread</th><th class="num">Updated</th></tr>
        </thead>
        <tbody>
          <tr v-for="quote in quotes" :key="quote.symbol" class="hoverable">
            <td style="font-weight: 600">{{ quote.symbol }}</td>
            <td style="width: 80px">
              <Sparkline :data="hist[quote.symbol] || [quote.bid, quote.bid]" :width="72" :height="22" :color="trendUp(quote.symbol) ? 'var(--pos)' : 'var(--neg)'" />
            </td>
            <td class="num" :style="{ color: quote.dir === 'up' ? 'var(--pos)' : quote.dir === 'down' ? 'var(--neg)' : 'var(--ink)' }">
              <Icon v-if="quote.dir" :name="quote.dir === 'up' ? 'up' : 'down'" :size="11" style="margin-right: 3px; vertical-align: -1px" />{{ quote.bid }}
            </td>
            <td class="num">{{ quote.ask }}</td>
            <td class="num muted">{{ quote.spread_points }}</td>
            <td class="num faint">{{ fmtTime(quote.time) }}</td>
          </tr>
          <tr v-if="!quotes.length"><td colspan="6" class="muted" style="padding: var(--sp-6)">Waiting for quotes…</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="errors.length" style="padding: 0 var(--sp-7) var(--sp-6)">
      <Notice v-if="hasBrokerSymbolError" tone="warn">
        US stocks are not automatically available through every MT5 broker.
        Try the broker's exact symbol name, or
        <RouterLink to="/settings/market-data">configure the free Alpaca IEX stock feed</RouterLink>.
      </Notice>
      <ul class="reasons">
        <li v-for="item in errors" :key="item.symbol">
          <strong>{{ item.symbol }}</strong>: {{ item.hint || item.error }}
        </li>
      </ul>
    </div>
  </Panel>
</template>

<style scoped>
.symbol-control { display: flex; gap: var(--sp-3); margin-bottom: var(--sp-5); }
.symbol-control input { flex: 1; }
@media (max-width: 620px) { .symbol-control { flex-direction: column; } }
</style>
