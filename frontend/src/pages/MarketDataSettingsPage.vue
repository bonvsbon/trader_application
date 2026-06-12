<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type MarketDataConfiguration } from "../api/client";

const config = ref<MarketDataConfiguration | null>(null);
const symbolsText = ref("");
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

function errorText(value: any, fallback: string) {
  const detail = value?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item: any) => item.msg).join("; ");
  return detail ?? value?.message ?? fallback;
}

async function load() {
  loading.value = true;
  try {
    config.value = await api.marketDataConfiguration();
    symbolsText.value = config.value.default_symbols.join(", ");
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Failed to load market-data configuration");
  } finally {
    loading.value = false;
  }
}

function providerChanged() {
  if (!config.value) return;
  config.value.enabled = config.value.provider !== "disabled";
  if (config.value.provider === "alpaca") {
    config.value.endpoint ||= "wss://stream.data.alpaca.markets/v2";
    config.value.api_key_ref ||= "MARKET_DATA_ALPACA_KEY";
    config.value.api_secret_ref ||= "MARKET_DATA_ALPACA_SECRET";
    if (symbolsText.value === "XAUUSD") symbolsText.value = "AAPL, MSFT, NVDA";
  }
}

async function save() {
  if (!config.value) return;
  config.value.default_symbols = Array.from(
    new Set(
      symbolsText.value
        .split(",")
        .map((value) => value.trim().toUpperCase())
        .filter(Boolean),
    ),
  );
  saving.value = true;
  message.value = null;
  try {
    config.value = await api.updateMarketDataConfiguration(config.value);
    symbolsText.value = config.value.default_symbols.join(", ");
    message.value = "Market-data configuration saved. Reconnect the watchlist to apply it.";
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Failed to save market-data configuration");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  testing.value = true;
  message.value = null;
  try {
    const result = await api.testMarketDataConfiguration();
    message.value = result.healthy
      ? `Connection healthy: ${result.provider} / ${result.feed_status} (${result.latency_ms} ms)`
      : `Connection failed: ${result.error}`;
  } catch (e: any) {
    error.value = errorText(e, "Market-data connection test failed");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Market Data</h2>
      <p class="sub">Configure the read-only realtime watchlist feed.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>
  <div v-if="message" class="notice success">{{ message }}</div>

  <section v-if="loading" class="panel">
    <div class="skeleton sk-line"></div>
    <div class="skeleton sk-line"></div>
  </section>

  <section v-else-if="config" class="panel editor">
    <div class="notice neutral">
      This feed powers the watchlist only. Risk checks and order execution continue to use MT5 broker quotes.
    </div>

    <div class="form-grid">
      <div class="field">
        <label>Provider</label>
        <select v-model="config.provider" @change="providerChanged">
          <option value="mt5">MT5 broker feed</option>
          <option value="alpaca">Alpaca stocks</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>
      <div class="field">
        <label>Enabled</label>
        <label class="switch-row">
          <input v-model="config.enabled" type="checkbox" :disabled="config.provider === 'disabled'" />
          <span>{{ config.enabled ? "Enabled" : "Disabled" }}</span>
        </label>
      </div>

      <template v-if="config.provider === 'alpaca'">
        <div class="field span-2">
          <label>WebSocket endpoint</label>
          <input v-model.trim="config.endpoint" />
          <small>Remote endpoints must use WSS and be allowed by the backend host allowlist.</small>
        </div>
        <div class="field">
          <label>Feed</label>
          <select v-model="config.feed">
            <option value="iex">IEX realtime</option>
            <option value="sip">SIP realtime (subscription required)</option>
            <option value="delayed_sip">Delayed SIP</option>
          </select>
        </div>
        <div class="field">
          <label>Feed status</label>
          <input :value="config.feed_status" disabled />
        </div>
        <div class="field">
          <label>API key environment reference</label>
          <input v-model.trim="config.api_key_ref" placeholder="MARKET_DATA_ALPACA_KEY" />
          <small>{{ config.api_key_configured ? "Configured" : "No environment value" }}</small>
        </div>
        <div class="field">
          <label>API secret environment reference</label>
          <input v-model.trim="config.api_secret_ref" placeholder="MARKET_DATA_ALPACA_SECRET" />
          <small>{{ config.api_secret_configured ? "Configured" : "No environment value" }}</small>
        </div>
      </template>

      <div class="field span-2">
        <label>Default symbols (comma separated)</label>
        <input v-model.trim="symbolsText" placeholder="XAUUSD or AAPL, MSFT, NVDA" />
      </div>
      <div class="field">
        <label>Maximum symbols</label>
        <input v-model.number="config.max_symbols" type="number" min="1" max="100" />
      </div>
      <div class="field">
        <label>Connection timeout (seconds)</label>
        <input v-model.number="config.timeout_sec" type="number" min="1" max="60" />
      </div>
    </div>

    <div class="actions">
      <button class="btn secondary" @click="testConnection" :disabled="testing || saving">
        <span v-if="testing" class="spin"></span>
        Test connection
      </button>
      <button class="btn" @click="save" :disabled="saving || testing">
        <span v-if="saving" class="spin"></span>
        Save configuration
      </button>
    </div>
  </section>
</template>

<style scoped>
.notice { margin-bottom: var(--sp-5); }
.notice.success { background: var(--allow-bg); color: var(--allow-fg); }
.notice.neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--sp-5); margin-top: var(--sp-6); }
.span-2 { grid-column: span 2; }
.field small { display: block; margin-top: var(--sp-2); color: var(--ink-muted); }
.switch-row { display: flex; align-items: center; gap: var(--sp-3); min-height: 40px; }
.switch-row input { width: auto; }
.actions { display: flex; justify-content: flex-end; gap: var(--sp-4); margin-top: var(--sp-6); }
@media (max-width: 620px) {
  .form-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: auto; }
  .actions { flex-direction: column; }
}
</style>
