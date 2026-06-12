<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "../api/client";

interface ClosedTrade {
  id: number;
  ticket: number;
  symbol: string;
  side: string | null;
  volume: number | null;
  profit: number;
  close_time: string | null;
  r_multiple: number | null;
  entry_price: number | null;
  exit_price: number | null;
  open_time: string | null;
  exit_reason: string | null;
  strategy_reason: string | null;
  ai_reason: string | null;
  decision: string | null;
}
interface Summary {
  count: number;
  wins: number;
  losses: number;
  win_rate_pct: number | null;
  net_pnl: number;
  total_r: number | null;
  avg_r: number | null;
  rated_count: number;
}
interface DailyRow extends Summary {
  date: string;
}

interface ReviewTrade extends ClosedTrade {
  reviewed: boolean;
  review_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
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

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id;
}
function hasJournal(t: ClosedTrade) {
  return !!(t.exit_reason || t.strategy_reason || t.ai_reason || t.decision || t.entry_price);
}

function fmt(ts: string | null) {
  return ts ? new Date(ts).toLocaleString() : "—";
}
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
  <div class="page-head row between">
    <div>
      <h2>Trade History</h2>
      <p class="sub">Closed trades synced from MT5, with realized P&amp;L and R-multiple.</p>
    </div>
    <div class="row" style="gap: var(--sp-3)">
      <button class="btn secondary sm" @click="backfill" :disabled="backfilling || loading">
        {{ backfilling ? "Backfilling…" : "Backfill 30d" }}
      </button>
      <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
    </div>
  </div>
  <p v-if="backfillMsg" class="sub" style="margin-top: calc(-1 * var(--sp-3)); margin-bottom: var(--sp-5)">{{ backfillMsg }}</p>

  <div class="cards" v-if="summary">
    <div class="card">
      <span class="lbl">Net P&amp;L</span>
      <span class="val mono" :class="signClass(summary.net_pnl)">{{ money(summary.net_pnl) }}</span>
    </div>
    <div class="card">
      <span class="lbl">Total R</span>
      <span class="val mono" :class="signClass(summary.total_r)">{{ rfmt(summary.total_r) }}</span>
    </div>
    <div class="card">
      <span class="lbl">Win rate</span>
      <span class="val mono">{{ summary.win_rate_pct === null ? "—" : summary.win_rate_pct.toFixed(0) + "%" }}</span>
      <span class="sub-lbl">{{ summary.wins }}W · {{ summary.losses }}L</span>
    </div>
    <div class="card">
      <span class="lbl">Avg R</span>
      <span class="val mono" :class="signClass(summary.avg_r)">{{ rfmt(summary.avg_r) }}</span>
      <span class="sub-lbl">{{ summary.rated_count }} rated</span>
    </div>
  </div>

  <section class="panel pad-tight">
    <div v-if="loading" class="stack" style="padding: var(--sp-4)">
      <div class="skeleton sk-line" v-for="i in 5" :key="i" :style="{ width: 90 - i * 6 + '%' }"></div>
    </div>

    <div v-else-if="!trades.length" class="empty">
      <div class="icon">▦</div>
      <div class="title">No closed trades yet</div>
      <p class="muted">Closed trades appear here after the interval workflow syncs them from MT5.</p>
    </div>

    <div v-else class="table-wrap">
      <table>
        <thead><tr><th></th><th>Closed</th><th>Symbol</th><th>Side</th><th class="num">Entry</th><th class="num">Exit</th><th class="num">P&amp;L</th><th class="num">R</th></tr></thead>
        <tbody>
          <template v-for="t in trades" :key="t.id">
            <tr class="trade-row" :class="{ open: expandedId === t.id, clickable: hasJournal(t) }" @click="hasJournal(t) && toggleExpand(t.id)">
              <td class="exp"><span v-if="hasJournal(t)" class="caret" :class="{ open: expandedId === t.id }">▸</span></td>
              <td class="muted mono">{{ fmt(t.close_time) }}</td>
              <td>{{ t.symbol }}</td>
              <td><span v-if="t.side" class="badge no-dot">{{ t.side }}</span><span v-else class="muted">—</span></td>
              <td class="num mono">{{ t.entry_price ?? "—" }}</td>
              <td class="num mono">{{ t.exit_price ?? "—" }}</td>
              <td class="num mono" :class="signClass(t.profit)">{{ money(t.profit) }}</td>
              <td class="num mono" :class="signClass(t.r_multiple)">{{ rfmt(t.r_multiple) }}</td>
            </tr>
            <tr v-if="expandedId === t.id" class="journal-row">
              <td></td>
              <td colspan="7">
                <div class="journal">
                  <div class="jv"><span class="jl">Exit reason</span><span class="mono">{{ t.exit_reason ?? "—" }}</span></div>
                  <div class="jv"><span class="jl">Opened</span><span class="mono muted">{{ fmt(t.open_time) }}</span></div>
                  <div class="jv"><span class="jl">Volume</span><span class="mono">{{ t.volume ?? "—" }}</span></div>
                  <div class="jv"><span class="jl">Risk decision</span><span v-if="t.decision" class="badge no-dot" :class="t.decision">{{ t.decision }}</span><span v-else class="muted">—</span></div>
                  <div class="jv wide"><span class="jl">Strategy reason</span><span>{{ t.strategy_reason ?? "—" }}</span></div>
                  <div class="jv wide"><span class="jl">AI note</span><span>{{ t.ai_reason ?? "—" }}</span></div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>

  <section v-if="daily.length" class="panel pad-tight daily-panel">
    <div class="panel-head"><span class="panel-title">By day</span></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Date</th><th class="num">Trades</th><th class="num">W/L</th><th class="num">Net P&amp;L</th><th class="num">R</th></tr></thead>
        <tbody>
          <tr v-for="d in daily" :key="d.date">
            <td class="mono">{{ d.date }}</td>
            <td class="num mono">{{ d.count }}</td>
            <td class="num mono muted">{{ d.wins }}/{{ d.losses }}</td>
            <td class="num mono" :class="signClass(d.net_pnl)">{{ money(d.net_pnl) }}</td>
            <td class="num mono" :class="signClass(d.total_r)">{{ rfmt(d.total_r) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section v-if="review.length" class="panel pad-tight review-panel">
    <div class="panel-head"><span class="panel-title">Loss review</span></div>
    <p class="sub" style="margin-bottom: var(--sp-5)">Record what went wrong on losing trades — a journal for improving the playbook.</p>
    <ul class="loss-list">
      <li v-for="t in review" :key="t.id" class="loss-item">
        <div class="loss-head">
          <span class="mono">{{ t.symbol }} <span v-if="t.side">· {{ t.side }}</span></span>
          <span class="mono neg">{{ money(t.profit) }}<span v-if="t.r_multiple !== null"> · {{ rfmt(t.r_multiple) }}</span></span>
          <span class="muted mono">{{ fmt(t.close_time) }}</span>
          <span v-if="t.reviewed" class="badge ALLOW no-dot">Reviewed</span>
        </div>
        <p v-if="t.reviewed" class="note">{{ t.review_note }}</p>
        <div v-else class="loss-edit">
          <textarea
            v-model="noteDraft[t.ticket]"
            rows="2"
            placeholder="What went wrong? (entry, sizing, news, discipline…)"
          ></textarea>
          <div class="loss-actions">
            <button class="btn secondary sm" :disabled="analyzingTicket === t.ticket" @click="analyzeReview(t.ticket)">
              {{ analyzingTicket === t.ticket ? "Analyzing…" : "AI draft" }}
            </button>
            <button class="btn sm" :disabled="savingTicket === t.ticket || !(noteDraft[t.ticket] || '').trim()" @click="saveReview(t.ticket)">
              {{ savingTicket === t.ticket ? "Saving…" : "Save review" }}
            </button>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--sp-4); margin-bottom: var(--sp-6); }
.card { display: flex; flex-direction: column; gap: 2px; padding: var(--sp-5); background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); }
.card .lbl { font-size: var(--text-xs); color: var(--ink-muted); }
.card .val { font-size: 1.5rem; font-weight: 600; letter-spacing: 0.01em; }
.card .sub-lbl { font-size: var(--text-xs); color: var(--ink-faint); }
.num { text-align: right; }
.trade-row.clickable { cursor: pointer; }
.trade-row .exp { width: 22px; color: var(--ink-faint); }
.caret { display: inline-block; transition: transform 0.15s ease; }
.caret.open { transform: rotate(90deg); }
.journal-row > td { background: var(--surface-2); padding: 0; }
.journal { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--sp-4) var(--sp-6); padding: var(--sp-5); }
.journal .jv { display: flex; flex-direction: column; gap: 2px; font-size: var(--text-sm); }
.journal .jv.wide { grid-column: 1 / -1; }
.journal .jl { font-size: var(--text-xs); color: var(--ink-muted); }
@media (prefers-reduced-motion: reduce) { .caret { transition: none; } }
.daily-panel { margin-top: var(--sp-6); }
.review-panel { margin-top: var(--sp-6); }
.loss-list { list-style: none; display: flex; flex-direction: column; gap: var(--sp-4); }
.loss-item { padding: var(--sp-4) 0; border-top: 1px solid var(--border); }
.loss-item:first-child { border-top: none; }
.loss-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-4); font-size: var(--text-sm); }
.loss-head .muted { margin-left: auto; }
.note { margin-top: var(--sp-3); color: var(--ink-muted); font-size: var(--text-sm); white-space: pre-wrap; }
.loss-edit { display: flex; gap: var(--sp-3); align-items: flex-start; margin-top: var(--sp-3); }
.loss-edit textarea { flex: 1; resize: vertical; }
.loss-actions { display: flex; flex-direction: column; gap: var(--sp-2); }
</style>
