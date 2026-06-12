<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  spread_points: number;
  time: string;
  dir?: "up" | "down" | "";
}

const symbolInput = ref("XAUUSD");
const quotes = ref<Quote[]>([]);
const errors = ref<Array<{ symbol: string; error: string }>>([]);
const source = ref("connecting");
const feedStatus = ref("unknown");
const connected = ref(false);
let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;

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
    }
    quotes.value = Array.from(merged.values());
    errors.value = payload.errors;
  };
  socket.onclose = () => {
    connected.value = false;
    reconnectTimer = window.setTimeout(connect, 3000);
  };
  socket.onerror = () => socket?.close();
}

function fmtTime(value: string) {
  return new Date(value).toLocaleTimeString();
}

onMounted(connect);
onUnmounted(() => {
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  socket?.close();
});
</script>

<template>
  <section class="panel watchlist">
    <div class="panel-head watchlist-head">
      <div>
        <span class="panel-title">Realtime Watchlist</span>
        <p class="watchlist-copy">
          Read-only quotes from the configured provider. Execution still uses the MT5 broker quote.
        </p>
      </div>
      <span class="badge" :class="connected ? 'HEALTHY' : 'UNKNOWN'">
        {{ connected ? `${source} · ${feedStatus}` : "RECONNECTING" }}
      </span>
    </div>

    <div class="symbol-control">
      <input
        v-model="symbolInput"
        aria-label="Watchlist symbols"
        placeholder="XAUUSD, AAPL, MSFT"
        @keyup.enter="connect"
      />
      <button class="btn secondary sm" @click="connect">Apply symbols</button>
    </div>

    <div v-if="source === 'mt5:mock'" class="notice warn">
      Mock bridge prices are synthetic test data, not live market prices.
    </div>

    <div v-if="quotes.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th class="num">Bid</th>
            <th class="num">Ask</th>
            <th class="num">Spread</th>
            <th class="num">Updated</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="quote in quotes" :key="quote.symbol">
            <td><strong>{{ quote.symbol }}</strong></td>
            <td class="num mono tick" :class="quote.dir">
              {{ quote.bid }}<span v-if="quote.dir" class="arrow">{{ quote.dir === "up" ? "▲" : "▼" }}</span>
            </td>
            <td class="num mono">{{ quote.ask }}</td>
            <td class="num mono">{{ quote.spread_points }}</td>
            <td class="num mono">{{ fmtTime(quote.time) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="muted">Waiting for quotes...</p>

    <ul v-if="errors.length" class="reasons">
      <li v-for="item in errors" :key="item.symbol">
        {{ item.symbol }}: {{ item.error }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.watchlist { margin-top: var(--sp-6); }
.watchlist-head { align-items: flex-start; }
.watchlist-copy { margin-top: var(--sp-2); color: var(--ink-muted); font-size: var(--text-sm); }
.symbol-control { display: flex; gap: var(--sp-3); margin: var(--sp-5) 0; }
.symbol-control input { flex: 1; }
.notice { margin-bottom: var(--sp-4); }
.num { text-align: right; }
.tick.up { color: var(--pos); }
.tick.down { color: var(--neg); }
.tick .arrow { margin-left: var(--sp-2); font-size: 0.7em; vertical-align: 1px; }
@media (max-width: 620px) {
  .symbol-control { flex-direction: column; }
}
</style>
