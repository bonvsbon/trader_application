<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  api,
  type StrategyPresetConfiguration,
  type TradeProposal,
} from "../api/client";

const config = ref<StrategyPresetConfiguration | null>(null);
const proposals = ref<TradeProposal[]>([]);
const setup = ref<{
  side: "BUY" | "SELL";
  sl: number | null;
  volume: number | null;
  strategy_reason: string;
}>({
  side: "BUY",
  sl: null,
  volume: null,
  strategy_reason: "",
});
const loading = ref(true);
const saving = ref(false);
const generating = ref(false);
const evaluating = ref(false);
const submitting = ref<number | null>(null);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

const backtest = ref<any>(null);
const backtesting = ref(false);
const backtestCount = ref(500);

function errorText(value: any, fallback: string) {
  return value?.response?.data?.detail ?? value?.message ?? fallback;
}

function fmt(value: string) {
  return new Date(value).toLocaleString();
}

function rfmt(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}R`;
}

function signClass(n: number | null | undefined) {
  if (!n) return "";
  return n > 0 ? "pos" : "neg";
}

async function runBacktest() {
  backtesting.value = true;
  message.value = null;
  try {
    backtest.value = await api.backtestSignal(backtestCount.value);
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Backtest failed");
  } finally {
    backtesting.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    [config.value, proposals.value] = await Promise.all([
      api.strategyConfiguration(),
      api.proposals(),
    ]);
    error.value = null;
  } catch (e: any) {
    error.value = errorText(e, "Failed to load strategy configuration");
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  if (!config.value) return;
  saving.value = true;
  message.value = null;
  try {
    config.value = await api.updateStrategyConfiguration(config.value);
    error.value = null;
    message.value = "Strategy preset saved.";
  } catch (e: any) {
    error.value = errorText(e, "Failed to save strategy preset");
  } finally {
    saving.value = false;
  }
}

async function generate() {
  if (!setup.value.sl || !setup.value.strategy_reason.trim()) {
    error.value = "Stop loss and setup reason are required.";
    return;
  }
  generating.value = true;
  message.value = null;
  try {
    const proposal = await api.generateProposal({
      side: setup.value.side,
      sl: setup.value.sl,
      volume: setup.value.volume || null,
      strategy_reason: setup.value.strategy_reason.trim(),
    });
    proposals.value.unshift(proposal);
    error.value = null;
    message.value = `Proposal #${proposal.id} generated with ${proposal.risk_decision} risk decision.`;
  } catch (e: any) {
    error.value = errorText(e, "Failed to generate proposal");
  } finally {
    generating.value = false;
  }
}

async function evaluateSignal() {
  evaluating.value = true;
  message.value = null;
  try {
    const result = await api.evaluateSignal();
    error.value = null;
    if (result.proposal) {
      proposals.value.unshift(result.proposal);
      message.value = `D40/D20 signal: ${result.signal.side} — proposal #${result.proposal.id} created (${result.proposal.risk_decision}).`;
    } else {
      message.value = `D40/D20 signal: ${result.reason}`;
    }
  } catch (e: any) {
    error.value = errorText(e, "Failed to evaluate signal");
  } finally {
    evaluating.value = false;
  }
}

async function submit(proposal: TradeProposal) {
  const confirmed = window.confirm(
    `Submit proposal #${proposal.id}: ${proposal.side} ${proposal.volume} ${proposal.symbol}?`,
  );
  if (!confirmed) return;
  submitting.value = proposal.id;
  try {
    const result = await api.submitProposal(proposal.id);
    message.value = `Proposal #${proposal.id}: ${result.message}`;
    error.value = null;
    proposals.value = await api.proposals();
  } catch (e: any) {
    error.value = errorText(e, "Failed to submit proposal");
  } finally {
    submitting.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Strategy & Proposals</h2>
      <p class="sub">Configurable XAUUSD D40/D20 preset and risk-checked trade drafts.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>
  <div v-if="message" class="notice success">{{ message }}</div>

  <div v-if="loading" class="grid">
    <div class="panel" v-for="i in 2" :key="i">
      <div class="skeleton sk-line"></div>
      <div class="skeleton sk-line"></div>
    </div>
  </div>

  <template v-else-if="config">
    <div class="grid strategy-grid">
      <section class="panel">
        <div class="panel-head">
          <span class="panel-title">Preset Configuration</span>
          <label class="switch-row">
            <input v-model="config.enabled" type="checkbox" />
            <span>Enabled</span>
          </label>
        </div>
        <div class="notice warn">
          D40/D20 = Donchian breakout: enter when the latest closed bar breaks the
          40-bar high/low; stop at the 20-bar channel; TP at the reward:risk ratio.
          Automatic signal evaluation stays off until you tick
          <strong>Confirm signal definition</strong>. Generated signals only create
          proposals — they never trade until you approve.
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Symbol</label>
            <input v-model.trim="config.symbol" />
          </div>
          <div class="field">
            <label>Preset name</label>
            <input v-model.trim="config.preset_name" />
          </div>
          <div class="field">
            <label>D40 value</label>
            <input v-model.number="config.d40_value" type="number" min="0.01" step="0.01" />
          </div>
          <div class="field">
            <label>D20 value</label>
            <input v-model.number="config.d20_value" type="number" min="0.01" step="0.01" />
          </div>
          <div class="field">
            <label>Reward / risk</label>
            <input v-model.number="config.reward_risk_ratio" type="number" min="0.1" max="10" step="0.1" />
          </div>
          <div class="field">
            <label>Risk %</label>
            <input v-model.number="config.risk_pct" type="number" min="0.01" step="0.01" />
          </div>
        </div>
        <label class="switch-row news-row">
          <input v-model="config.require_news_clear" type="checkbox" />
          <span>Require news filter to be clear</span>
        </label>
        <label class="switch-row news-row">
          <input v-model="config.signal_definition_confirmed" type="checkbox" />
          <span>Confirm signal definition (enables automatic D40/D20 evaluation)</span>
        </label>
        <div class="panel-actions">
          <button
            class="btn secondary"
            @click="evaluateSignal"
            :disabled="evaluating || !config.enabled || !config.signal_definition_confirmed"
          >
            <span v-if="evaluating" class="spin"></span>
            Evaluate D40/D20 now
          </button>
          <button class="btn" @click="saveConfig" :disabled="saving">
            <span v-if="saving" class="spin"></span>
            Save preset
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><span class="panel-title">Manual Proposal Builder</span></div>
        <div class="field">
          <label>Side</label>
          <select v-model="setup.side">
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div class="field">
          <label>Stop loss</label>
          <input v-model.number="setup.sl" type="number" step="0.01" placeholder="Required" />
        </div>
        <div class="field">
          <label>Volume (optional)</label>
          <input v-model.number="setup.volume" type="number" min="0.01" step="0.01" placeholder="Auto-size from risk" />
        </div>
        <div class="field">
          <label>Setup reason</label>
          <textarea v-model.trim="setup.strategy_reason" rows="4" placeholder="Why this D40/D20 setup is valid"></textarea>
        </div>
        <button class="btn full" @click="generate" :disabled="generating || !config.enabled">
          <span v-if="generating" class="spin"></span>
          Generate risk-checked proposal
        </button>
      </section>
    </div>

    <section class="panel backtest-panel">
      <div class="panel-head bt-head">
        <span class="panel-title">Signal backtest · D{{ config.d40_value }}/D{{ config.d20_value }}</span>
        <div class="bt-controls">
          <input
            v-model.number="backtestCount"
            type="number"
            min="50"
            max="5000"
            step="50"
            aria-label="Number of candles to test"
          />
          <button class="btn secondary sm" @click="runBacktest" :disabled="backtesting">
            <span v-if="backtesting" class="spin"></span>
            Run backtest
          </button>
        </div>
      </div>
      <div class="notice warn">
        Idealized rule check on the last N closed candles (close-to-close fills, fixed
        reward:risk, no spread/slippage/commission). A sanity check on the signal
        definition — <strong>not</strong> a profitability forecast.
      </div>
      <template v-if="backtest">
        <div class="bt-cards">
          <div class="bt-card">
            <span class="lbl">Trades</span>
            <span class="val mono">{{ backtest.trades }}</span>
            <span class="sub-lbl">{{ backtest.wins }}W · {{ backtest.losses }}L<span v-if="backtest.open_trades"> · {{ backtest.open_trades }} open</span></span>
          </div>
          <div class="bt-card">
            <span class="lbl">Win rate</span>
            <span class="val mono">{{ backtest.trades ? (backtest.win_rate * 100).toFixed(0) + "%" : "—" }}</span>
          </div>
          <div class="bt-card">
            <span class="lbl">Total R</span>
            <span class="val mono" :class="signClass(backtest.total_r)">{{ rfmt(backtest.total_r) }}</span>
          </div>
          <div class="bt-card">
            <span class="lbl">Avg R</span>
            <span class="val mono" :class="signClass(backtest.avg_r)">{{ rfmt(backtest.avg_r) }}</span>
          </div>
          <div class="bt-card">
            <span class="lbl">Max drawdown</span>
            <span class="val mono neg">{{ backtest.max_drawdown_r ? "−" + backtest.max_drawdown_r.toFixed(2) + "R" : "0.00R" }}</span>
          </div>
        </div>
        <p class="sub bt-meta">
          {{ backtest.candles }} candles · reward:risk {{ backtest.reward_risk }} · timeframe from preset
        </p>
      </template>
      <p v-else class="muted">Run a backtest to evaluate the current preset over recent candles.</p>
    </section>

    <section class="panel pad-tight">
      <div class="panel-head proposal-head">
        <span class="panel-title">Recent Proposals</span>
        <span class="muted">{{ proposals.length }} total</span>
      </div>
      <div v-if="!proposals.length" class="empty">
        <div class="title">No proposals yet</div>
        <p>Enable the preset and create a manual setup above.</p>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr><th>Created</th><th>Setup</th><th class="num">Entry</th><th class="num">SL</th><th class="num">TP</th><th class="num">Lot</th><th>Risk</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="proposal in proposals" :key="proposal.id">
              <td class="mono muted">{{ fmt(proposal.created_at) }}</td>
              <td><strong>{{ proposal.side }}</strong> {{ proposal.symbol }}</td>
              <td class="num">{{ proposal.entry_price }}</td>
              <td class="num">{{ proposal.sl }}</td>
              <td class="num">{{ proposal.tp.toFixed(2) }}</td>
              <td class="num">{{ proposal.volume }}</td>
              <td><span class="badge" :class="proposal.risk_decision">{{ proposal.risk_decision }}</span></td>
              <td><span class="badge" :class="proposal.status">{{ proposal.status }}</span></td>
              <td>
                <button
                  v-if="proposal.status === 'DRAFT'"
                  class="btn sm"
                  @click="submit(proposal)"
                  :disabled="submitting !== null"
                >
                  <span v-if="submitting === proposal.id" class="spin"></span>
                  Submit
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>

<style scoped>
.notice { margin-bottom: var(--sp-5); }
.notice.success { background: var(--allow-bg); color: var(--allow-fg); }
.notice.warn { background: var(--warn-bg); color: var(--warn-fg); font-size: var(--text-sm); }
.strategy-grid { grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.7fr); margin-bottom: var(--sp-6); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--sp-5); }
.switch-row { display: flex; align-items: center; gap: var(--sp-4); cursor: pointer; }
.switch-row input { width: auto; }
.news-row { color: var(--ink-muted); }
.panel-actions { display: flex; justify-content: flex-end; gap: var(--sp-4); margin-top: var(--sp-5); flex-wrap: wrap; }
.full { width: 100%; }
.proposal-head { padding: var(--sp-5) var(--sp-6) 0; }
.backtest-panel { margin-bottom: var(--sp-6); }
.bt-head { flex-wrap: wrap; gap: var(--sp-4); }
.bt-controls { display: flex; align-items: center; gap: var(--sp-3); }
.bt-controls input { width: 96px; }
.backtest-panel .notice.warn { margin: var(--sp-5) 0; }
.bt-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--sp-4); }
.bt-card { display: flex; flex-direction: column; gap: 2px; padding: var(--sp-5); background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md); }
.bt-card .lbl { font-size: var(--text-xs); color: var(--ink-muted); }
.bt-card .val { font-size: var(--text-xl); font-weight: 650; letter-spacing: 0.01em; }
.bt-card .sub-lbl { font-size: var(--text-xs); color: var(--ink-faint); }
.bt-meta { margin-top: var(--sp-5); }
@media (max-width: 850px) {
  .strategy-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
