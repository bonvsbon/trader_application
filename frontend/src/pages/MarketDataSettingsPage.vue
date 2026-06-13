<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { api, type MarketDataConfiguration } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Field from "../components/ui/Field.vue";
import Toggle from "../components/ui/Toggle.vue";
import Notice from "../components/ui/Notice.vue";

const config = ref<MarketDataConfiguration | null>(null);
const symbolsText = ref("");
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

const isAlpaca = computed(() => config.value?.provider === "alpaca");

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
    new Set(symbolsText.value.split(",").map((v) => v.trim().toUpperCase()).filter(Boolean)),
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
  <div class="stack">
    <PageHead title="Market Data" sub="Realtime price feed for the watchlist">
      <template #actions>
        <Badge v-if="config" :tone="config.enabled ? 'allow' : 'warn'">{{ config.enabled ? "FEED ENABLED" : "DISABLED" }}</Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>
    <Notice v-if="message" tone="success">{{ message }}</Notice>

    <div v-if="loading && !config" class="panel panel-pad"><div class="sk-line" /><div class="sk-line" style="margin-top: 8px" /></div>

    <Panel v-else-if="config" title="Feed configuration">
      <div class="stack">
        <Toggle
          label="Feed enabled"
          sub="Streams quotes to the watchlist only"
          :checked="config.enabled"
          @change="config.provider !== 'disabled' && (config.enabled = $event)"
        />
        <div class="form-grid">
          <Field label="Provider">
            <select v-model="config.provider" @change="providerChanged">
              <option value="mt5">MT5 broker feed</option>
              <option value="alpaca">Alpaca stocks</option>
              <option value="disabled">Disabled</option>
            </select>
          </Field>
          <Field v-if="isAlpaca" label="Feed">
            <select v-model="config.feed">
              <option value="iex">IEX realtime</option>
              <option value="sip">SIP realtime (subscription required)</option>
              <option value="delayed_sip">Delayed SIP</option>
            </select>
          </Field>
          <Field v-if="isAlpaca" class="full" label="WebSocket endpoint" hint="ws:// or wss:// · remote endpoints must use WSS and be allowlisted">
            <input class="mono" v-model.trim="config.endpoint" />
          </Field>
          <Field v-if="isAlpaca" label="Feed status" hint="read-only · derived from provider + feed">
            <input class="mono" :value="config.feed_status" readonly />
          </Field>
          <Field class="full" label="Default symbols" hint="comma separated">
            <input class="mono" v-model.trim="symbolsText" placeholder="XAUUSD or AAPL, MSFT, NVDA" />
          </Field>
          <Field label="Maximum symbols"><input class="mono" v-model.number="config.max_symbols" type="number" min="1" max="100" /></Field>
          <Field label="Connection timeout (s)"><input class="mono" v-model.number="config.timeout_sec" type="number" min="1" max="60" /></Field>
          <Field v-if="isAlpaca" label="API key env reference" :hint="config.api_key_configured ? 'configured' : 'no environment value'">
            <input class="mono" v-model.trim="config.api_key_ref" placeholder="MARKET_DATA_ALPACA_KEY" />
          </Field>
          <Field v-if="isAlpaca" label="API secret env reference" :hint="config.api_secret_configured ? 'configured' : 'no environment value'">
            <input class="mono" v-model.trim="config.api_secret_ref" placeholder="MARKET_DATA_ALPACA_SECRET" />
          </Field>
        </div>
        <Notice :tone="isAlpaca ? 'warn' : 'neutral'">
          <template v-if="isAlpaca">Alpaca supplies the watchlist and analysis only. Order risk and execution prices always come from the MT5 broker quote. API keys are stored as environment references, never as raw values.</template>
          <template v-else>Order risk and execution always use the MT5 broker quote. This feed drives the watchlist display only. Keys are stored as environment references.</template>
        </Notice>
        <div class="row" style="gap: var(--sp-4)">
          <Btn variant="secondary" icon="database" :loading="testing" :disabled="testing || saving" @click="testConnection">Test connection</Btn>
          <Btn icon="save" :loading="saving" :disabled="saving || testing" @click="save">Save configuration</Btn>
        </div>
      </div>
    </Panel>
  </div>
</template>
