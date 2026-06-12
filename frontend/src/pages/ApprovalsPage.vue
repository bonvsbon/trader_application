<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const orders = ref<any[]>([]);
const loading = ref(true);
const handling = ref<string | null>(null);
const error = ref<string | null>(null);
const message = ref<string | null>(null);

function fmt(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

function confidencePct(value: number | null | undefined) {
  return value == null ? null : `${Math.round(value * 100)}%`;
}

async function load() {
  loading.value = true;
  try {
    orders.value = await api.pendingApprovals();
    error.value = null;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Failed to load approvals";
  } finally {
    loading.value = false;
  }
}

async function approve(order: any) {
  const confirmed = window.confirm(
    `Approve ${order.side} ${order.volume} ${order.symbol}? Risk will be checked again before execution.`,
  );
  if (!confirmed) return;
  handling.value = order.idempotency_key;
  try {
    const result = await api.approveOrder(order.idempotency_key);
    message.value = `${order.symbol}: ${result.message}`;
    error.value = null;
    await load();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Approval failed";
  } finally {
    handling.value = null;
  }
}

async function reject(order: any) {
  const confirmed = window.confirm(`Reject ${order.side} ${order.volume} ${order.symbol}?`);
  if (!confirmed) return;
  handling.value = order.idempotency_key;
  try {
    const result = await api.rejectOrder(order.idempotency_key);
    message.value = `${order.symbol}: ${result.message}`;
    error.value = null;
    await load();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Rejection failed";
  } finally {
    handling.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-head row between">
    <div>
      <h2>Approval Queue</h2>
      <p class="sub">Orders waiting for human review. Risk is recalculated at approval time.</p>
    </div>
    <button class="btn secondary sm" @click="load" :disabled="loading">Refresh</button>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>
  <div v-if="message" class="notice success">{{ message }}</div>

  <div v-if="loading" class="stack">
    <div class="panel" v-for="i in 2" :key="i">
      <div class="skeleton sk-line"></div>
      <div class="skeleton sk-line"></div>
      <div class="skeleton sk-line"></div>
    </div>
  </div>

  <section v-else-if="!orders.length" class="panel">
    <div class="empty">
      <div class="title">No orders awaiting approval</div>
      <p>Real-account and warning decisions will appear here with their risk and AI context.</p>
    </div>
  </section>

  <div v-else class="approval-list">
    <article class="panel approval-card" v-for="order in orders" :key="order.id">
      <header class="ac-head">
        <div class="ac-title">
          <span class="side" :class="order.side">{{ order.side }}</span>
          <span class="sym">{{ order.symbol }}</span>
          <span class="badge" :class="order.account_type">{{ order.account_type }}</span>
          <span class="badge" :class="order.decision" v-if="order.decision">{{ order.decision }}</span>
        </div>
        <span class="mono muted ac-time">{{ fmt(order.created_at) }}</span>
      </header>

      <div class="ac-facts">
        <div class="fact"><span class="k">Volume</span><span class="v mono">{{ order.volume }}</span></div>
        <div class="fact"><span class="k">Stop loss</span><span class="v mono">{{ order.sl ?? "—" }}</span></div>
        <div class="fact"><span class="k">Take profit</span><span class="v mono">{{ order.tp ?? "—" }}</span></div>
        <div class="fact"><span class="k">Risk %</span><span class="v mono">{{ order.risk_pct ?? "—" }}</span></div>
        <div class="fact"><span class="k">Requested by</span><span class="v">{{ order.requested_by }}</span></div>
      </div>

      <div class="ac-section" v-if="order.risk_reasons?.length || order.risk_warnings?.length">
        <span class="ac-label">Why this needs approval</span>
        <ul class="reasons" v-if="order.risk_reasons?.length">
          <li v-for="(r, i) in order.risk_reasons" :key="`r-${i}`">{{ r }}</li>
        </ul>
        <ul class="reasons warn" v-if="order.risk_warnings?.length">
          <li v-for="(w, i) in order.risk_warnings" :key="`w-${i}`">{{ w }}</li>
        </ul>
      </div>

      <div
        class="ac-section"
        v-if="order.strategy_reason || order.proposal?.strategy_reason || order.ai_reason || order.proposal?.ai_summary"
      >
        <span class="ac-label">
          Strategy &amp; AI context
          <span class="badge no-dot src" v-if="order.proposal">Proposal #{{ order.proposal.id }}</span>
        </span>
        <p class="ctx" v-if="order.strategy_reason || order.proposal?.strategy_reason">
          <span class="tag">Setup</span>{{ order.strategy_reason || order.proposal?.strategy_reason }}
        </p>
        <template v-if="order.ai_reason || order.proposal?.ai_summary">
          <p class="ctx">
            <span class="tag ai">AI</span>{{ order.ai_reason || order.proposal?.ai_summary }}
            <span class="muted" v-if="confidencePct(order.proposal?.ai_confidence)">
              · confidence {{ confidencePct(order.proposal?.ai_confidence) }}
            </span>
          </p>
          <p class="advisory faint">AI is advisory only — it never approves or places an order.</p>
        </template>
      </div>

      <footer class="ac-actions">
        <button class="btn danger sm" @click="reject(order)" :disabled="handling !== null">
          Reject
        </button>
        <button class="btn sm" @click="approve(order)" :disabled="handling !== null">
          <span v-if="handling === order.idempotency_key" class="spin"></span>
          Approve
        </button>
      </footer>
    </article>
  </div>
</template>

<style scoped>
.notice { margin-bottom: var(--sp-5); }
.notice.success { background: var(--allow-bg); color: var(--allow-fg); }

.approval-list { display: flex; flex-direction: column; gap: var(--sp-6); }
.approval-card { display: flex; flex-direction: column; gap: var(--sp-6); }

.ac-head { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-5); flex-wrap: wrap; }
.ac-title { display: flex; align-items: center; gap: var(--sp-4); flex-wrap: wrap; }
.ac-title .side { font-weight: 700; letter-spacing: 0.02em; }
.ac-title .side.BUY { color: var(--pos); }
.ac-title .side.SELL { color: var(--neg); }
.ac-title .sym { font-weight: 600; font-size: var(--text-md); }
.ac-time { font-size: var(--text-xs); }

.ac-facts {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--sp-5) var(--sp-6);
  padding: var(--sp-5) 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
}
.fact { display: flex; flex-direction: column; gap: var(--sp-2); }
.fact .k { font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted); }
.fact .v { font-weight: 600; }

.ac-section { display: flex; flex-direction: column; gap: var(--sp-3); }
.ac-label {
  display: flex; align-items: center; gap: var(--sp-4);
  font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--ink-muted); font-weight: 600;
}
.ac-label .src { text-transform: none; letter-spacing: 0; }
.ac-section .reasons { margin-top: 0; }

.ctx { font-size: var(--text-sm); line-height: 1.55; }
.tag {
  display: inline-block; margin-right: var(--sp-4); padding: 1px 7px; border-radius: var(--r-sm);
  font-size: var(--text-xs); font-weight: 650; letter-spacing: 0.03em;
  background: var(--neutral-bg); color: var(--ink-muted); vertical-align: 1px;
}
.tag.ai { background: color-mix(in oklab, var(--accent) 16%, transparent); color: var(--accent-ink); }
.advisory { font-size: var(--text-xs); }

.ac-actions { display: flex; justify-content: flex-end; gap: var(--sp-4); }
</style>
