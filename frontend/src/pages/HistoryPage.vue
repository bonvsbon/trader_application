<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { api } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Icon from "../components/ui/Icon.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import Donut from "../components/ui/Donut.vue";
import MiniBars from "../components/ui/MiniBars.vue";
import { badgeClass } from "../components/ui/badge";

interface ClosedTrade {
  id: number; ticket: number; symbol: string; side: string | null; volume: number | null;
  profit: number; close_time: string | null; r_multiple: number | null;
  entry_price: number | null; exit_price: number | null; open_time: string | null;
  exit_reason: string | null; strategy_reason: string | null; ai_reason: string | null; decision: string | null;
}
interface Summary {
  count: number; wins: number; losses: number; win_rate_pct: number | null;
  net_pnl: number; total_r: number | null; avg_r: number | null; rated_count: number;
}
interface DailyRow extends Summary { date: string; }
interface ReviewTrade extends ClosedTrade {
  reviewed: boolean; review_note: string | null; reviewed_by: string | null; reviewed_at: string | null;
}

const trades = ref<ClosedTrade[]>([]);
const summary = ref<Summary | null>(null);
const daily = ref<DailyRow[]>([]);
const review = ref<ReviewTrade[]>([]);
const noteDraft = ref<Record<number, string>>({});
const savingTicket = ref<number | null>(null);
const analyzingTicket = ref<number | null>(null);
const loading = ref(true);
const expandedId = ref<number | null>(null);
const backfilling = ref(false);
const backfillMsg = ref<string | null>(null);

function toggleExpand(id: number) { expandedId.value = expandedId.value === id ? null : id; }
function hasJournal(t: ClosedTrade) {
  return !!(t.exit_reason || t.strategy_reason || t.ai_reason || t.decision || t.entry_price);
}
function fmt(ts: string | null) { return ts ? new Date(ts).toLocaleString() : "—"; }
function money(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return `${n < 0 ? "−" : ""}$${Math.abs(n).toFixed(2)}`;
}
function rfmt(n: number | null) {
  if (n === null || n === undefined) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}R`;
}
function signClass(n: number | null | undefined) {
  if (n === null || n === undefined || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}

const dailyBars = computed(() =>
  [...daily.value].reverse().map((d) => ({ v: d.net_pnl, label: `${d.date}: ${money(d.net_pnl)}` })),
);

async function load() {
  loading.value = true;
  try {
    [trades.value, summary.value, daily.value, review.value] = await Promise.all([
      api.historyTrades(), api.historySummary(), api.historyDaily(), api.historyReview(),
    ]);
  } catch { /* backend down */ }
  finally { loading.value = false; }
}

async function backfill() {
  backfilling.value = true;
  backfillMsg.value = null;
  try {
    const r = await api.historyBackfill(30);
    backfillMsg.value = `Backfill: fetched ${r.fetched}, added ${r.inserted} (last ${r.days} days)`;
    await load();
  } catch (e: any) {
    backfillMsg.value = e?.response?.data?.detail ?? "Backfill failed";
  } finally {
    backfilling.value = false;
  }
}

async function saveReview(ticket: number) {
  const note = (noteDraft.value[ticket] ?? "").trim();
  if (!note) return;
  savingTicket.value = ticket;
  try {
    await api.saveTradeReview(ticket, note);
    review.value = await api.historyReview();
    delete noteDraft.value[ticket];
  } catch { /* keep draft on failure */ }
  finally { savingTicket.value = null; }
}

async function analyzeReview(ticket: number) {
  analyzingTicket.value = ticket;
  try {
    const result = await api.analyzeTradeReview(ticket);
    noteDraft.value[ticket] = result.summary ?? "No enabled healthy loss-review provider.";
  } catch (e: any) {
    noteDraft.value[ticket] = e?.response?.data?.detail ?? "AI review unavailable.";
  } finally {
    analyzingTicket.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="stack">
    <PageHead title="Trade History" sub="Closed trades — realized P&L and R-multiple">
      <template #actions>
        <Btn sm variant="secondary" icon="clock" :loading="backfilling" :disabled="backfilling || loading" @click="backfill">Backfill 30d</Btn>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>
    <Notice v-if="backfillMsg" tone="neutral">{{ backfillMsg }}</Notice>

    <div class="hist-cols">
      <Panel title="Performance">
        <div v-if="summary" class="row" style="gap: var(--sp-8); align-items: center">
          <Donut :value="summary.win_rate_pct ?? 0" :label="summary.win_rate_pct === null ? '—' : `${summary.win_rate_pct.toFixed(0)}%`" sub="win rate" color="var(--allow-fg)" :size="104" :stroke="10" />
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-6) var(--sp-8); flex: 1">
            <div class="col" style="gap: 4px">
              <span class="stat-l">Net P&amp;L</span>
              <span class="mono stat-v" :class="signClass(summary.net_pnl)">{{ money(summary.net_pnl) }}</span>
            </div>
            <div class="col" style="gap: 4px">
              <span class="stat-l">Total R</span>
              <span class="mono stat-v" :class="signClass(summary.total_r)">{{ rfmt(summary.total_r) }}</span>
            </div>
            <div class="col" style="gap: 4px">
              <span class="stat-l">Win rate</span>
              <span class="mono stat-v">{{ summary.win_rate_pct === null ? "—" : summary.win_rate_pct.toFixed(0) + "%" }}</span>
              <span class="faint mono" style="font-size: var(--text-xs)">{{ summary.wins }}W · {{ summary.losses }}L</span>
            </div>
            <div class="col" style="gap: 4px">
              <span class="stat-l">Avg R</span>
              <span class="mono stat-v" :class="signClass(summary.avg_r)">{{ rfmt(summary.avg_r) }}</span>
              <span class="faint mono" style="font-size: var(--text-xs)">{{ summary.rated_count }} rated</span>
            </div>
          </div>
        </div>
        <EmptyState v-else icon="history" title="No performance data" desc="Closed trades populate these metrics." />
      </Panel>

      <Panel title="Daily P&L">
        <div v-if="dailyBars.length" class="col" style="gap: var(--sp-5)">
          <MiniBars :data="dailyBars" :height="64" />
          <div class="row between">
            <div v-for="d in [...daily].reverse()" :key="d.date" class="col" style="gap: 2px; align-items: center; flex: 1">
              <span class="faint" style="font-size: var(--text-xs)">{{ d.date.slice(5) }}</span>
              <span class="mono" :class="signClass(d.net_pnl)" style="font-size: var(--text-xs); font-weight: 600">{{ money(d.net_pnl) }}</span>
            </div>
          </div>
        </div>
        <EmptyState v-else icon="market" title="No daily data" desc="Per-day P&L appears here." />
      </Panel>
    </div>

    <Panel title="Trades" :pad="false">
      <div v-if="loading && !trades.length" class="stack" style="padding: var(--sp-6)">
        <div class="sk-line" v-for="i in 5" :key="i" :style="{ width: 90 - i * 6 + '%' }" />
      </div>
      <EmptyState v-else-if="!trades.length" icon="history" title="No closed trades yet" desc="Closed trades appear here after the interval workflow syncs them from MT5." />
      <div v-else class="table-wrap">
        <table class="tbl">
          <thead><tr><th style="width: 28px"></th><th>Ticket</th><th>Side</th><th>Closed</th><th class="num">Entry</th><th class="num">Exit</th><th class="num">P&amp;L</th><th class="num">R</th></tr></thead>
          <tbody>
            <template v-for="t in trades" :key="t.id">
              <tr class="hoverable" :style="{ cursor: hasJournal(t) ? 'pointer' : 'default' }" @click="hasJournal(t) && toggleExpand(t.id)">
                <td><Icon v-if="hasJournal(t)" name="caret" :size="14" :style="{ transform: expandedId === t.id ? 'rotate(90deg)' : 'none', transition: 'transform .18s', color: 'var(--ink-faint)' }" /></td>
                <td class="mono">{{ t.ticket }}</td>
                <td :style="{ color: t.side === 'BUY' ? 'var(--allow-fg)' : t.side === 'SELL' ? 'var(--block-fg)' : 'var(--ink-muted)', fontWeight: 600 }">{{ t.side ?? "—" }}</td>
                <td class="muted">{{ fmt(t.close_time) }}</td>
                <td class="num">{{ t.entry_price ?? "—" }}</td>
                <td class="num">{{ t.exit_price ?? "—" }}</td>
                <td class="num" :class="signClass(t.profit)" style="font-weight: 600">{{ money(t.profit) }}</td>
                <td class="num" :class="signClass(t.r_multiple)">{{ rfmt(t.r_multiple) }}</td>
              </tr>
              <tr v-if="expandedId === t.id">
                <td></td>
                <td colspan="7" style="background: var(--surface-2)">
                  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--sp-5); padding: var(--sp-3) 0">
                    <div class="col" style="gap: 3px"><span class="jl">Exit reason</span><span style="font-weight: 500">{{ t.exit_reason ?? "—" }}</span></div>
                    <div class="col" style="gap: 3px"><span class="jl">Opened</span><span class="muted">{{ fmt(t.open_time) }}</span></div>
                    <div class="col" style="gap: 3px"><span class="jl">Volume</span><span style="font-weight: 500">{{ t.volume ?? "—" }} lots</span></div>
                    <div class="col" style="gap: 3px"><span class="jl">Risk decision</span><span><Badge v-if="t.decision" :tone="badgeClass(t.decision)" no-dot>{{ t.decision }}</Badge><span v-else class="muted">—</span></span></div>
                    <div class="col" style="gap: 3px; grid-column: 1 / -1"><span class="jl">Strategy</span><span>{{ t.strategy_reason ?? "—" }}</span></div>
                    <div class="col" style="gap: 3px; grid-column: 1 / -1"><span class="jl">AI note</span><span class="muted" style="font-size: var(--text-sm)">{{ t.ai_reason ?? "—" }}</span></div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </Panel>

    <Panel v-if="daily.length" title="By day" :pad="false">
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Date</th><th class="num">Trades</th><th class="num">W / L</th><th class="num">Net P&amp;L</th><th class="num">R</th></tr></thead>
          <tbody>
            <tr v-for="d in daily" :key="d.date" class="hoverable">
              <td style="font-weight: 600">{{ d.date }}</td>
              <td class="num muted">{{ d.count }}</td>
              <td class="num muted">{{ d.wins }} / {{ d.losses }}</td>
              <td class="num" :class="signClass(d.net_pnl)" style="font-weight: 600">{{ money(d.net_pnl) }}</td>
              <td class="num" :class="signClass(d.total_r)">{{ rfmt(d.total_r) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>

    <Panel v-if="review.length" title="Loss review">
      <p class="muted" style="font-size: var(--text-sm); margin: 0 0 var(--sp-5)">Record what went wrong on losing trades — a journal for improving the playbook.</p>
      <ul class="loss-list">
        <li v-for="t in review" :key="t.id" class="loss-item">
          <div class="loss-head">
            <span class="mono">{{ t.symbol }}<span v-if="t.side"> · {{ t.side }}</span></span>
            <span class="mono neg">{{ money(t.profit) }}<span v-if="t.r_multiple !== null"> · {{ rfmt(t.r_multiple) }}</span></span>
            <span class="muted mono" style="margin-left: auto">{{ fmt(t.close_time) }}</span>
            <Badge v-if="t.reviewed" tone="allow" no-dot>Reviewed</Badge>
          </div>
          <p v-if="t.reviewed" class="note">{{ t.review_note }}</p>
          <div v-else class="loss-edit">
            <textarea v-model="noteDraft[t.ticket]" rows="2" placeholder="What went wrong? (entry, sizing, news, discipline…)" />
            <div class="loss-actions">
              <Btn sm variant="secondary" icon="sparkle" :loading="analyzingTicket === t.ticket" :disabled="analyzingTicket === t.ticket" @click="analyzeReview(t.ticket)">AI draft</Btn>
              <Btn sm icon="save" :loading="savingTicket === t.ticket" :disabled="savingTicket === t.ticket || !(noteDraft[t.ticket] || '').trim()" @click="saveReview(t.ticket)">Save review</Btn>
            </div>
          </div>
        </li>
      </ul>
    </Panel>
  </div>
</template>

<style scoped>
.hist-cols { display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--sp-6); }
@media (max-width: 880px) { .hist-cols { grid-template-columns: 1fr; } }
.stat-l { font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-faint); }
.stat-v { font-size: var(--text-xl); font-weight: 700; letter-spacing: -0.01em; }
.jl { font-size: var(--text-xs); color: var(--ink-faint); text-transform: uppercase; }
.loss-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.loss-item { padding: var(--sp-5) 0; border-top: 1px solid var(--border); }
.loss-item:first-child { border-top: none; padding-top: 0; }
.loss-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-4); font-size: var(--text-sm); }
.note { margin-top: var(--sp-3); color: var(--ink-muted); font-size: var(--text-sm); white-space: pre-wrap; }
.loss-edit { display: flex; gap: var(--sp-4); align-items: flex-start; margin-top: var(--sp-3); }
.loss-edit textarea { flex: 1; }
.loss-actions { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
