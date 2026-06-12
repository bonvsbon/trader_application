<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type Mt5Configuration } from "../api/client";

const account = ref<any>(null);
const config = ref<Mt5Configuration | null>(null);
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

function errorText(value: any, fallback: string) {
  return value?.response?.data?.detail ?? value?.message ?? fallback;
}

async function load() {
  loading.value = true;
  try {
    const [accountResult, configResult] = await Promise.all([
      api.account(),
      api.accountConfiguration(),
    ]);
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
    (!config.value.expected_login ||
      !config.value.expected_server ||
      config.value.expected_account_type === "UNKNOWN")
  ) {
    error.value = "Live EA bridge requires expected login, server, and DEMO/REAL account type.";
    return;
  }
  const confirmed = window.confirm(
    "Save MT5 configuration? The workflow will stop and the bridge will restart.",
  );
  if (!confirmed) return;
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
  <div class="page-head row between">
    <div>
      <h2>MT5 Account</h2>
      <p class="sub">Connection status and editable account allowlist configuration.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>
  <div v-if="message" class="notice success">{{ message }}</div>

  <div v-if="loading" class="grid">
    <div class="panel" v-for="i in 3" :key="i">
      <div class="skeleton sk-line" style="width: 35%"></div>
      <div class="skeleton sk-line" style="width: 70%"></div>
      <div class="skeleton sk-line" style="width: 55%"></div>
    </div>
  </div>

  <template v-else>
    <div v-if="account" class="grid status-grid">
      <section class="panel">
        <div class="panel-head"><span class="panel-title">Connection</span></div>
        <div class="kv"><span class="label">Bridge health</span><span class="value"><span class="badge" :class="account.bridge_health">{{ account.bridge_health }}</span></span></div>
        <div class="kv"><span class="label">Config match</span><span class="value"><span class="badge" :class="account.configuration_match ? 'ALLOW' : 'BLOCK'">{{ account.configuration_match ? "MATCH" : "MISMATCH" }}</span></span></div>
        <div class="kv"><span class="label">Last heartbeat</span><span class="value mono">{{ account.last_heartbeat ? new Date(account.last_heartbeat).toLocaleTimeString() : "—" }}</span></div>
        <div class="kv"><span class="label">Detail</span><span class="value muted">{{ account.detail || "—" }}</span></div>
        <ul v-if="account.configuration_problems?.length" class="reasons">
          <li v-for="problem in account.configuration_problems" :key="problem">{{ problem }}</li>
        </ul>
      </section>

      <section class="panel" v-if="account.account">
        <div class="panel-head">
          <span class="panel-title">Connected Account</span>
          <span class="badge" :class="account.account.account_type">{{ account.account.account_type }}</span>
        </div>
        <div class="kv"><span class="label">Login</span><span class="value mono">{{ account.account.login ?? "—" }}</span></div>
        <div class="kv"><span class="label">Server</span><span class="value">{{ account.account.server ?? "—" }}</span></div>
        <div class="kv"><span class="label">Balance</span><span class="value mono">{{ account.account.balance?.toLocaleString() }} {{ account.account.currency }}</span></div>
        <div class="kv"><span class="label">Equity</span><span class="value mono">{{ account.account.equity?.toLocaleString() }}</span></div>
        <div class="kv"><span class="label">Free margin</span><span class="value mono">{{ account.account.free_margin?.toLocaleString() }} ({{ account.account.free_margin_pct }}%)</span></div>
        <div class="kv"><span class="label">Leverage</span><span class="value mono">1:{{ account.account.leverage }}</span></div>
      </section>
    </div>

    <section v-if="config" class="panel config-panel">
      <div class="panel-head">
        <div>
          <span class="panel-title">Runtime Configuration</span>
          <p class="config-meta">
            Source: {{ config.source ?? "database" }}
            <span v-if="config.updated_by"> · Updated by {{ config.updated_by }}</span>
          </p>
        </div>
        <label class="switch-row">
          <input v-model="config.enabled" type="checkbox" />
          <span>Enabled</span>
        </label>
      </div>

      <div class="notice neutral">
        MT5 password is never accepted or stored here. Sign in inside MT5 Terminal;
        this config defines which connected account is allowed to trade.
        EA socket authentication uses <code>MT5_EA_SHARED_SECRET</code>, which
        must match the EA input and is never stored in this form.
      </div>

      <div class="form-grid">
        <div class="field">
          <label>Bridge type</label>
          <select v-model="config.bridge_type">
            <option value="mock">Mock (local testing)</option>
            <option value="ea_socket">EA socket (MT5)</option>
          </select>
        </div>
        <div class="field">
          <label>Backend listen host</label>
          <input v-model.trim="config.host" placeholder="127.0.0.1" />
        </div>
        <div class="field">
          <label>Backend listen port</label>
          <input v-model.number="config.port" type="number" min="1" max="65535" />
        </div>
        <div class="field">
          <label>Request timeout (seconds)</label>
          <input v-model.number="config.timeout_sec" type="number" min="0.1" max="60" step="0.1" />
        </div>
        <div class="field">
          <label>Heartbeat max age (seconds)</label>
          <input v-model.number="config.heartbeat_max_age_sec" type="number" min="1" max="300" />
        </div>
        <div class="field">
          <label>Expected MT5 login</label>
          <input v-model.number="config.expected_login" type="number" min="1" placeholder="Required for EA socket" />
        </div>
        <div class="field">
          <label>Expected MT5 server</label>
          <input v-model.trim="config.expected_server" placeholder="Broker-Demo" />
        </div>
        <div class="field">
          <label>Expected account type</label>
          <select v-model="config.expected_account_type">
            <option value="UNKNOWN">Not restricted (mock only)</option>
            <option value="DEMO">DEMO</option>
            <option value="REAL">REAL</option>
          </select>
        </div>
      </div>

      <div class="config-actions">
        <button class="btn secondary" @click="testConnection" :disabled="testing || saving">
          <span v-if="testing" class="spin"></span>
          Test current connection
        </button>
        <button class="btn" @click="save" :disabled="saving || testing">
          <span v-if="saving" class="spin"></span>
          Save and restart bridge
        </button>
      </div>
      <p class="muted safety-note">
        Selecting REAL does not enable real trading. Backend safety flags and operator
        authentication remain mandatory.
        EA shared secret:
        {{ config.ea_shared_secret_configured ? "configured" : "not configured" }}.
      </p>
    </section>
  </template>
</template>

<style scoped>
.status-grid { margin-bottom: var(--sp-6); }
.config-panel { margin-top: var(--sp-6); }
.config-meta { margin-top: var(--sp-2); color: var(--ink-muted); font-size: var(--text-xs); }
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0 var(--sp-6);
  margin-top: var(--sp-7);
}
.switch-row { display: flex; align-items: center; gap: var(--sp-4); cursor: pointer; }
.switch-row input { width: auto; }
.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-4);
  margin-top: var(--sp-4);
}
.notice { margin-bottom: var(--sp-5); }
.notice.success { background: var(--allow-bg); color: var(--allow-fg); }
.notice.neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
.safety-note { margin-top: var(--sp-5); text-align: right; font-size: var(--text-xs); }
@media (max-width: 640px) {
  .config-actions { flex-direction: column-reverse; }
  .config-actions .btn { width: 100%; }
}
</style>
