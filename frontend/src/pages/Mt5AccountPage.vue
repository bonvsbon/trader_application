<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { api, type Mt5Configuration } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Kv from "../components/ui/Kv.vue";
import Field from "../components/ui/Field.vue";
import Toggle from "../components/ui/Toggle.vue";
import Notice from "../components/ui/Notice.vue";
import Reasons from "../components/ui/Reasons.vue";
import { badgeClass } from "../components/ui/badge";

const account = ref<any>(null);
const config = ref<Mt5Configuration | null>(null);
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

const isReal = computed(() => config.value?.expected_account_type === "REAL");

function errorText(value: any, fallback: string) {
  return value?.response?.data?.detail ?? value?.message ?? fallback;
}

async function load() {
  loading.value = true;
  try {
    const [accountResult, configResult] = await Promise.all([api.account(), api.accountConfiguration()]);
    account.value = accountResult;
    config.value = configResult;
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Failed to load MT5 account configuration");
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!config.value) return;
  if (
    config.value.bridge_type === "ea_socket" &&
    (!config.value.expected_login || !config.value.expected_server || config.value.expected_account_type === "UNKNOWN")
  ) {
    error.value = "Live EA bridge requires expected login, server, and DEMO/REAL account type.";
    return;
  }
  if (!window.confirm("Save MT5 configuration? The workflow will stop and the bridge will restart.")) return;
  saving.value = true;
  message.value = null;
  try {
    const result = await api.updateAccountConfiguration(config.value);
    config.value = result.configuration;
    account.value = result.connection;
    error.value = null;
    message.value = "Configuration saved. Workflow stopped and MT5 bridge restarted.";
  } catch (e: any) {
    error.value = errorText(e, "Failed to save MT5 configuration");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  testing.value = true;
  message.value = null;
  try {
    account.value = await api.testAccountConfiguration();
    error.value = null;
    message.value = account.value.configuration_match
      ? "Connection and configured account match."
      : "Bridge responded, but the connected account does not match the configuration.";
  } catch (e: any) {
    error.value = errorText(e, "MT5 connection test failed");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="stack">
    <PageHead title="MT5 Account" sub="Connection status and bridge configuration">
      <template #actions>
        <Badge v-if="account" :tone="badgeClass(account.bridge_health)">{{ account.bridge_health }}</Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>
    <Notice v-if="message" tone="success">{{ message }}</Notice>

    <div v-if="loading && !config" class="grid">
      <div class="panel panel-pad" v-for="i in 2" :key="i"><div class="sk-line" style="width: 35%" /><div class="sk-line" style="width: 70%; margin-top: 8px" /><div class="sk-line" style="width: 55%; margin-top: 8px" /></div>
    </div>

    <template v-else>
      <div v-if="account" class="grid">
        <Panel title="Connection">
          <Kv k="Bridge health"><Badge :tone="badgeClass(account.bridge_health)">{{ account.bridge_health }}</Badge></Kv>
          <Kv k="Config match"><Badge :tone="account.configuration_match ? 'allow' : 'block'" no-dot>{{ account.configuration_match ? "MATCH" : "MISMATCH" }}</Badge></Kv>
          <Kv k="Last heartbeat" :v="account.last_heartbeat ? new Date(account.last_heartbeat).toLocaleTimeString() : '—'" mono />
          <Kv k="Detail"><span class="faint" style="font-weight: 400; font-size: var(--text-xs)">{{ account.detail || "—" }}</span></Kv>
          <Reasons v-if="account.configuration_problems?.length" :items="account.configuration_problems" />
        </Panel>

        <Panel v-if="account.account" title="Connected account">
          <template #action><Badge :tone="badgeClass(account.account.account_type)">{{ account.account.account_type }}</Badge></template>
          <Kv k="Login" :v="account.account.login ?? '—'" mono />
          <Kv k="Server" :v="account.account.server ?? '—'" mono />
          <Kv k="Balance" :v="`${account.account.balance?.toLocaleString()} ${account.account.currency ?? ''}`" mono />
          <Kv k="Equity" :v="account.account.equity?.toLocaleString()" mono tone="pos" />
          <Kv k="Free margin" :v="`${account.account.free_margin?.toLocaleString()} (${account.account.free_margin_pct}%)`" mono />
          <Kv k="Leverage" :v="`1:${account.account.leverage}`" mono />
        </Panel>
      </div>

      <Panel v-if="config" title="Runtime configuration">
        <div class="stack">
          <Toggle label="Bridge enabled" sub="Master switch for the MT5 connection" :checked="config.enabled" @change="config.enabled = $event" />
          <div class="form-grid">
            <Field label="Bridge type">
              <select v-model="config.bridge_type">
                <option value="mock">Mock (local testing)</option>
                <option value="ea_socket">EA socket (MT5)</option>
              </select>
            </Field>
            <Field label="Request timeout (s)"><input class="mono" v-model.number="config.timeout_sec" type="number" min="0.1" max="60" step="0.1" /></Field>
            <Field label="Backend listen host"><input class="mono" v-model.trim="config.host" placeholder="127.0.0.1" /></Field>
            <Field label="Backend listen port"><input class="mono" v-model.number="config.port" type="number" min="1" max="65535" /></Field>
            <Field label="Heartbeat max age (s)"><input class="mono" v-model.number="config.heartbeat_max_age_sec" type="number" min="1" max="300" /></Field>
            <Field label="Expected MT5 login"><input class="mono" v-model.number="config.expected_login" type="number" min="1" placeholder="Required for EA socket" /></Field>
            <Field label="Expected server"><input class="mono" v-model.trim="config.expected_server" placeholder="Broker-Demo" /></Field>
            <Field label="Expected account type">
              <select v-model="config.expected_account_type">
                <option value="UNKNOWN">Not restricted (mock only)</option>
                <option value="DEMO">DEMO</option>
                <option value="REAL">REAL</option>
              </select>
            </Field>
          </div>
          <Notice :tone="isReal ? 'warn' : 'neutral'">
            <template v-if="isReal">REAL selected. Choosing REAL does not enable live trading on its own — execution still requires the safety flags and per-order approval. Passwords are never stored; the EA shared secret is read from an environment variable.</template>
            <template v-else>Passwords are never stored. The EA shared secret (<code>MT5_EA_SHARED_SECRET</code>) is supplied via an environment variable, never through this form. Source: {{ config.source ?? "database" }}<span v-if="config.updated_by"> · updated by {{ config.updated_by }}</span>.</template>
          </Notice>
          <div class="row" style="gap: var(--sp-4)">
            <Btn variant="secondary" icon="plug" :loading="testing" :disabled="testing || saving" @click="testConnection">Test current connection</Btn>
            <Btn icon="save" :variant="isReal ? 'danger' : undefined" :loading="saving" :disabled="saving || testing" @click="save">Save and restart bridge</Btn>
          </div>
          <span class="hint">EA shared secret: {{ config.ea_shared_secret_configured ? "configured" : "not configured" }}. Selecting REAL does not enable real trading — safety flags and operator authentication remain mandatory.</span>
        </div>
      </Panel>
    </template>
  </div>
</template>
