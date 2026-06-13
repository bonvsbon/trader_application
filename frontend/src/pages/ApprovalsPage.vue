<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Reasons from "../components/ui/Reasons.vue";
import Notice from "../components/ui/Notice.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import Icon from "../components/ui/Icon.vue";
import { badgeClass } from "../components/ui/badge";

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
  if (!window.confirm(`Approve ${order.side} ${order.volume} ${order.symbol}? Risk will be checked again before execution.`)) return;
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
  if (!window.confirm(`Reject ${order.side} ${order.volume} ${order.symbol}?`)) return;
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
  <div class="stack">
    <PageHead title="Approval Queue" sub="Orders awaiting a human decision · risk is re-checked at approval">
      <template #actions>
        <Badge :tone="orders.length ? 'warn' : 'allow'">{{ orders.length }} pending</Badge>
        <Btn sm variant="secondary" icon="refresh" :loading="loading" @click="load">Refresh</Btn>
      </template>
    </PageHead>

    <Notice v-if="error">{{ error }}</Notice>
    <Notice v-if="message" tone="success">{{ message }}</Notice>

    <template v-if="loading && !orders.length">
      <div class="panel panel-pad" v-for="i in 2" :key="i">
        <div class="sk-line" style="width: 40%" /><div class="sk-line" style="width: 70%; margin-top: 8px" /><div class="sk-line" style="width: 55%; margin-top: 8px" />
      </div>
    </template>

    <Panel v-else-if="!orders.length">
      <EmptyState icon="approvals" title="No orders awaiting approval" desc="Real-account and warn-level orders queue here for a second sign-off." />
    </Panel>

    <Panel v-for="order in orders" :key="order.id" :pad="false">
      <div class="panel-head" style="align-items: flex-start">
        <div class="row wrap" style="gap: var(--sp-4)">
          <span style="font-weight: 700; font-size: var(--text-md)" :style="{ color: order.side === 'BUY' ? 'var(--allow-fg)' : 'var(--block-fg)' }">{{ order.side }}</span>
          <span style="font-weight: 650; font-size: var(--text-md)">{{ order.symbol }}</span>
          <Badge :tone="order.account_type === 'DEMO' ? 'allow' : 'block'">{{ order.account_type }}</Badge>
          <Badge v-if="order.decision" :tone="badgeClass(order.decision)">{{ order.decision }}</Badge>
        </div>
        <span class="faint mono" style="font-size: var(--text-xs)">{{ fmt(order.created_at) }}</span>
      </div>

      <div class="panel-pad stack">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--sp-5)">
          <div class="col" v-for="cell in [
            ['Volume', order.volume],
            ['Stop loss', order.sl ?? '—'],
            ['Take profit', order.tp ?? '—'],
            ['Risk %', (order.risk_pct ?? '—') + '%'],
            ['Requested by', order.requested_by],
          ]" :key="cell[0]" style="gap: 3px">
            <span class="faint" style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em">{{ cell[0] }}</span>
            <span class="mono" style="font-weight: 600">{{ cell[1] }}</span>
          </div>
        </div>

        <div v-if="order.risk_reasons?.length || order.risk_warnings?.length">
          <div class="panel-title" style="margin-bottom: var(--sp-4)">Why this needs approval</div>
          <Reasons v-if="order.risk_reasons?.length" :items="order.risk_reasons" />
          <Reasons v-if="order.risk_warnings?.length" :items="order.risk_warnings" warn />
        </div>

        <div
          v-if="order.strategy_reason || order.proposal?.strategy_reason || order.ai_reason || order.proposal?.ai_summary"
          style="background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--sp-5)"
        >
          <div class="row wrap" style="gap: var(--sp-4); margin-bottom: var(--sp-4)">
            <span class="panel-title">Strategy &amp; AI context</span>
            <Badge v-if="order.proposal" tone="accent" no-dot>Proposal #{{ order.proposal.id }}</Badge>
          </div>
          <div v-if="order.strategy_reason || order.proposal?.strategy_reason" class="kv" style="padding-top: 0">
            <span class="k">Setup</span><span class="v" style="font-weight: 500; max-width: 60ch">{{ order.strategy_reason || order.proposal?.strategy_reason }}</span>
          </div>
          <template v-if="order.ai_reason || order.proposal?.ai_summary">
            <div class="kv"><span class="k">AI summary</span><span class="v" style="font-weight: 400; max-width: 60ch; color: var(--ink-muted)">{{ order.ai_reason || order.proposal?.ai_summary }}</span></div>
            <div v-if="confidencePct(order.proposal?.ai_confidence)" class="kv"><span class="k">AI confidence</span><span class="v mono">{{ confidencePct(order.proposal?.ai_confidence) }}</span></div>
          </template>
          <div class="faint" style="font-size: var(--text-xs); margin-top: var(--sp-4); display: flex; gap: 6px; align-items: center">
            <Icon name="info" :size="13" /> AI is advisory only — it never approves or places orders.
          </div>
        </div>

        <div class="row" style="gap: var(--sp-4); justify-content: flex-end">
          <Btn variant="danger" icon="x" :disabled="handling !== null" @click="reject(order)">Reject</Btn>
          <Btn icon="check" :loading="handling === order.idempotency_key" :disabled="handling !== null" @click="approve(order)">Approve</Btn>
        </div>
      </div>
    </Panel>
  </div>
</template>
