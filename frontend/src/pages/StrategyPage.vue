<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  api,
  type StrategyPresetConfiguration,
  type TradeProposal,
} from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Field from "../components/ui/Field.vue";
import Toggle from "../components/ui/Toggle.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { badgeClass } from "../components/ui/badge";

const config = ref<StrategyPresetConfiguration | null>(null);
const proposals = ref<TradeProposal[]>([]);
const setup = ref<{ side: "BUY" | "SELL"; sl: number | null; volume: number | null; strategy_reason: string }>({
  side: "BUY", sl: null, volume: null, strategy_reason: "",
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
function fmt(value: string) { return new Date(value).toLocaleString(); }
function rfmt(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}R`;
}
function signTone(n: number | null | undefined) {
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
    [config.value, proposals.value] = await Promise.all([api.strategyConfiguration(), api.proposals()]);
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
    setup.value.strategy_reason = "";
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
  if (!window.confirm(`Submit proposal #${proposal.id}: ${proposal.side} ${proposal.volume} ${proposal.symbol}?`)) return;
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
  <div class="stack">
    <PageHead title="Strategy & Proposals" sub="Donchian D40/D20 preset · proposal builder · signal backtest">
      <template #actions>
        <Badge v-if="config" :tone="config.enabled ? 'allow' : 'warn'">{{ config.enabled ? "PRESET ENABLED" : "DISABLED" }}</Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>
    <Notice v-if="message" tone="success">{{ message }}</Notice>

    <div v-if="loading && !config" class="grid">
      <div class="panel panel-pad" v-for="i in 2" :key="i"><div class="sk-line" /><div class="sk-line" style="margin-top: 8px" /></div>
    </div>

    <template v-else-if="config">
      <div class="strat-cols">
        <Panel title="Preset configuration">
          <div class="stack">
            <Toggle label="Strategy enabled" sub="When off, no automatic D40/D20 evaluation runs" :checked="config.enabled" @change="config.enabled = $event" />
            <div class="form-grid">
              <Field label="Symbol"><input v-model.trim="config.symbol" /></Field>
              <Field label="Preset name"><input v-model.trim="config.preset_name" /></Field>
              <Field label="D40 (entry channel)"><input class="mono" v-model.number="config.d40_value" type="number" min="0.01" step="0.01" /></Field>
              <Field label="D20 (exit channel)"><input class="mono" v-model.number="config.d20_value" type="number" min="0.01" step="0.01" /></Field>
              <Field label="Reward / risk"><input class="mono" v-model.number="config.reward_risk_ratio" type="number" min="0.1" max="10" step="0.1" /></Field>
              <Field label="Risk % per trade"><input class="mono" v-model.number="config.risk_pct" type="number" min="0.01" step="0.01" /></Field>
            </div>
            <hr class="hr" />
            <Toggle label="Require news filter clear" sub="Block evaluation when high-impact news is near" :checked="config.require_news_clear" @change="config.require_news_clear = $event" />
            <Toggle label="Confirm signal definition" sub="Enables automatic D40/D20 evaluation" :checked="config.signal_definition_confirmed" @change="config.signal_definition_confirmed = $event" />
            <Notice tone="warn">D40/D20 = Donchian breakout: enter on a 40-period channel break, trail the exit on the 20-period channel. Evaluation only sizes a <span class="mono">DRAFT</span> proposal — it never sends an order.</Notice>
            <div class="row" style="gap: var(--sp-4)">
              <Btn variant="secondary" icon="target" :loading="evaluating" :disabled="evaluating || !config.enabled || !config.signal_definition_confirmed" @click="evaluateSignal">Evaluate D40/D20 now</Btn>
              <Btn icon="save" :loading="saving" @click="saveConfig">Save preset</Btn>
            </div>
            <span v-if="!config.enabled || !config.signal_definition_confirmed" class="hint">Enable the strategy and confirm the signal definition to evaluate.</span>
          </div>
        </Panel>

        <div class="stack">
          <Panel title="Manual proposal builder">
            <div class="stack">
              <Field label="Side">
                <div class="seg" :class="setup.side === 'BUY' ? 'buy' : 'sell'">
                  <button :data-on="setup.side === 'BUY'" @click="setup.side = 'BUY'">BUY</button>
                  <button :data-on="setup.side === 'SELL'" @click="setup.side = 'SELL'">SELL</button>
                </div>
              </Field>
              <div class="form-grid">
                <Field label="Stop loss" req><input class="mono" v-model.number="setup.sl" type="number" step="0.01" /></Field>
                <Field label="Volume" hint="optional · auto-size"><input class="mono" v-model.number="setup.volume" type="number" min="0.01" step="0.01" placeholder="auto" /></Field>
              </div>
              <Field label="Setup reason"><textarea v-model.trim="setup.strategy_reason" placeholder="Why is this a valid setup?" /></Field>
              <Btn icon="check" full :loading="generating" :disabled="generating || !config.enabled" @click="generate">Generate risk-checked proposal</Btn>
            </div>
          </Panel>

          <Panel title="Signal backtest">
            <template #action><span class="faint" style="font-size: var(--text-xs)">read-only</span></template>
            <div class="stack">
              <div class="row" style="gap: var(--sp-4)">
                <Field label="Candles"><input class="mono" v-model.number="backtestCount" type="number" min="50" max="5000" step="50" style="width: 110px" /></Field>
                <Btn variant="secondary" icon="history" :loading="backtesting" :disabled="backtesting" style="align-self: flex-end" @click="runBacktest">Run backtest</Btn>
              </div>
              <div v-if="backtest" class="fade-in stack">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(86px, 1fr)); gap: var(--sp-4)">
                  <div class="col" style="gap: 2px"><span class="bt-l">Trades</span><span class="mono bt-v">{{ backtest.trades }}</span></div>
                  <div class="col" style="gap: 2px"><span class="bt-l">Win rate</span><span class="mono bt-v">{{ backtest.trades ? (backtest.win_rate * 100).toFixed(0) + "%" : "—" }}</span></div>
                  <div class="col" style="gap: 2px"><span class="bt-l">Total R</span><span class="mono bt-v" :class="signTone(backtest.total_r)">{{ rfmt(backtest.total_r) }}</span></div>
                  <div class="col" style="gap: 2px"><span class="bt-l">Avg R</span><span class="mono bt-v" :class="signTone(backtest.avg_r)">{{ rfmt(backtest.avg_r) }}</span></div>
                  <div class="col" style="gap: 2px"><span class="bt-l">Max DD</span><span class="mono bt-v neg">{{ backtest.max_drawdown_r ? "−" + backtest.max_drawdown_r.toFixed(2) + "R" : "0.00R" }}</span></div>
                </div>
                <Notice tone="neutral">Idealized rule check on {{ backtest.wins }}W / {{ backtest.losses }}L<span v-if="backtest.open_trades"> / {{ backtest.open_trades }} open</span> over {{ backtest.candles }} candles · reward:risk {{ backtest.reward_risk }} — not a profitability forecast.</Notice>
              </div>
              <p v-else class="muted" style="font-size: var(--text-sm); margin: 0">Run a backtest to evaluate the current preset over recent candles.</p>
            </div>
          </Panel>
        </div>
      </div>

      <Panel title="Recent proposals" :pad="false">
        <template #action><span class="faint" style="font-size: var(--text-xs)">{{ proposals.length }} total</span></template>
        <EmptyState v-if="!proposals.length" icon="strategy" title="No proposals yet" desc="Enable the preset and create a manual setup above." />
        <div v-else class="table-wrap" style="padding: var(--sp-3)">
          <table class="tbl">
            <thead><tr><th>Created</th><th>Setup</th><th class="num">Entry</th><th class="num">SL</th><th class="num">TP</th><th class="num">Lot</th><th>Risk</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in proposals" :key="p.id" class="hoverable">
                <td class="mono muted">{{ fmt(p.created_at) }}</td>
                <td><span :style="{ color: p.side === 'BUY' ? 'var(--allow-fg)' : 'var(--block-fg)', fontWeight: 600 }">{{ p.side }}</span> <span class="muted">{{ p.symbol }}</span></td>
                <td class="num">{{ p.entry_price }}</td>
                <td class="num">{{ p.sl }}</td>
                <td class="num">{{ p.tp.toFixed(2) }}</td>
                <td class="num">{{ p.volume }}</td>
                <td><Badge :tone="badgeClass(p.risk_decision)">{{ p.risk_decision }}</Badge></td>
                <td><Badge :tone="badgeClass(p.status)" no-dot>{{ p.status }}</Badge></td>
                <td style="text-align: right">
                  <Btn v-if="p.status === 'DRAFT'" sm icon="send" :loading="submitting === p.id" :disabled="submitting !== null" @click="submit(p)">Submit</Btn>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </template>
  </div>
</template>

<style scoped>
.strat-cols { display: grid; grid-template-columns: 1.2fr 1fr; gap: var(--sp-6); align-items: start; }
@media (max-width: 880px) { .strat-cols { grid-template-columns: 1fr; } }
.bt-l { font-size: var(--text-xs); text-transform: uppercase; color: var(--ink-faint); }
.bt-v { font-weight: 700; }
</style>
