<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { api, type OrderResult, type OrderTicket, type RiskPreview } from "../api/client";

const form = ref<OrderTicket>({ symbol: "XAUUSD", side: "BUY", volume: 0.1, sl: null, tp: null, risk_pct: 1.0 });
const accountType = ref<string>("UNKNOWN");
const result = ref<OrderResult | null>(null);
const preview = ref<RiskPreview | null>(null);
const previewError = ref<string | null>(null);
const busy = ref(false);
const confirmDialog = ref<HTMLDialogElement | null>(null);

const isReal = computed(() => accountType.value === "REAL");

function closeConfirm() { confirmDialog.value?.close(); }
function onBackdrop(e: MouseEvent) { if (e.target === confirmDialog.value) closeConfirm(); }

async function loadAccount() {
  try { accountType.value = (await api.account()).account?.account_type ?? "UNKNOWN"; }
  catch { accountType.value = "UNKNOWN"; }
}

async function doSubmit() {
  closeConfirm();
  busy.value = true;
  try { result.value = await api.submitOrder(form.value); }
  catch (e: any) { result.value = { ...(e?.response?.data ?? {}), message: e?.message ?? "Request failed" } as OrderResult; }
  finally { busy.value = false; }
}

async function checkPreview(): Promise<boolean> {
  busy.value = true;
  previewError.value = null;
  try {
    preview.value = await api.previewOrder(form.value);
    return preview.value.decision !== "BLOCK";
  } catch (e: any) {
    previewError.value = e?.response?.data?.detail?.[0]?.msg ?? e?.message ?? "Preview failed";
    return false;
  } finally {
    busy.value = false;
  }
}

async function onSubmit() {
  if (!(await checkPreview())) return;
  if (isReal.value) confirmDialog.value?.showModal(); // real money: confirm first
  else doSubmit();
}

async function approve() {
  if (!result.value) return;
  busy.value = true;
  try { result.value = await api.approveOrder(result.value.idempotency_key); }
  finally { busy.value = false; }
}
async function reject() {
  if (!result.value) return;
  busy.value = true;
  try { result.value = await api.rejectOrder(result.value.idempotency_key); }
  finally { busy.value = false; }
}
async function reconcile() {
  if (!result.value) return;
  busy.value = true;
  try { result.value = await api.reconcileOrder(result.value.idempotency_key); }
  finally { busy.value = false; }
}

onMounted(loadAccount);
</script>

<template>
  <div class="page-head">
    <h2>Manual Order</h2>
    <p class="sub">Every order passes the Risk Manager before it can reach the broker.</p>
  </div>

  <div class="order-layout">
    <section class="panel ticket">
      <div class="panel-head">
        <span class="panel-title">Order ticket</span>
        <span class="badge" :class="accountType">{{ accountType }}</span>
      </div>

      <div class="row" style="gap: var(--sp-5)">
        <div class="field" style="flex: 1"><label>Symbol</label><input v-model="form.symbol" /></div>
        <div class="field" style="flex: 1"><label>Side</label><select v-model="form.side"><option>BUY</option><option>SELL</option></select></div>
      </div>
      <div class="row" style="gap: var(--sp-5)">
        <div class="field" style="flex: 1"><label>Volume (lots)</label><input type="number" step="0.01" min="0.01" v-model.number="form.volume" /></div>
        <div class="field" style="flex: 1"><label>Risk %</label><input type="number" step="0.1" min="0.1" v-model.number="form.risk_pct" required /></div>
      </div>
      <div class="row" style="gap: var(--sp-5)">
        <div class="field" style="flex: 1"><label>Stop loss</label><input type="number" step="0.01" v-model.number="form.sl" placeholder="required" required /></div>
        <div class="field" style="flex: 1"><label>Take profit</label><input type="number" step="0.01" v-model.number="form.tp" placeholder="optional" /></div>
      </div>

      <button class="btn secondary" style="width: 100%; margin-top: var(--sp-3)" :disabled="busy" @click="checkPreview">
        Check size and risk
      </button>
      <button class="btn" style="width: 100%; margin-top: var(--sp-3)" :disabled="busy" @click="onSubmit">
        <span v-if="busy" class="spin"></span>
        {{ isReal ? "Review real-account order" : "Submit order" }}
      </button>
      <p class="faint" style="margin-top: var(--sp-4); font-size: var(--text-xs)">
        {{ isReal ? "Real account: you will confirm, then approve before execution." : "Demo account: filled immediately if risk checks pass." }}
      </p>
      <p v-if="previewError" class="notice" style="margin-top: var(--sp-4)">{{ previewError }}</p>
    </section>

    <section v-if="preview && !result" class="panel result">
      <div class="panel-head">
        <span class="panel-title">Risk preview</span>
        <span class="badge lg" :class="preview.decision">{{ preview.decision }}</span>
      </div>
      <div class="kv"><span class="label">Entry</span><span class="value mono">{{ preview.sizing.entry_price ?? "—" }}</span></div>
      <div class="kv"><span class="label">Estimated loss</span><span class="value mono neg">{{ preview.sizing.estimated_loss == null ? "—" : `$${preview.sizing.estimated_loss.toFixed(2)}` }}</span></div>
      <div class="kv"><span class="label">Estimated reward</span><span class="value mono pos">{{ preview.sizing.estimated_reward == null ? "—" : `$${preview.sizing.estimated_reward.toFixed(2)}` }}</span></div>
      <div class="kv"><span class="label">Actual risk</span><span class="value mono">{{ preview.sizing.sized_risk_pct == null ? "—" : `${preview.sizing.sized_risk_pct.toFixed(2)}%` }}</span></div>
      <div class="kv"><span class="label">Max lot for risk</span><span class="value mono">{{ preview.sizing.max_volume_for_risk ?? "—" }}</span></div>
      <div class="kv"><span class="label">Projected portfolio risk</span><span class="value mono">{{ preview.sizing.projected_portfolio_risk_pct == null ? "—" : `${preview.sizing.projected_portfolio_risk_pct.toFixed(2)}%` }}</span></div>
      <ul v-if="preview.reasons.length" class="reasons"><li v-for="(r, i) in preview.reasons" :key="i">{{ r }}</li></ul>
      <ul v-if="preview.warnings.length" class="reasons warn"><li v-for="(w, i) in preview.warnings" :key="i">{{ w }}</li></ul>
    </section>

    <section v-else-if="result" class="panel result">
      <div class="panel-head"><span class="panel-title">Result</span></div>
      <div class="row" style="gap: var(--sp-4)">
        <span class="badge lg" :class="result.decision">{{ result.decision }}</span>
        <span class="badge" :class="result.state">{{ result.state }}</span>
      </div>
      <p style="margin-top: var(--sp-5)">{{ result.message }}</p>
      <ul v-if="result.reasons?.length" class="reasons"><li v-for="(r, i) in result.reasons" :key="i">{{ r }}</li></ul>
      <ul v-if="result.warnings?.length" class="reasons warn"><li v-for="(w, i) in result.warnings" :key="i">{{ w }}</li></ul>

      <div v-if="result.state === 'PENDING_APPROVAL'" class="row" style="margin-top: var(--sp-6); gap: var(--sp-4)">
        <button class="btn" :disabled="busy" @click="approve">Approve and execute</button>
        <button class="btn secondary" :disabled="busy" @click="reject">Reject order</button>
      </div>
      <button
        v-if="result.state === 'RECONCILIATION_REQUIRED' || result.state === 'SUBMITTED'"
        class="btn secondary"
        style="margin-top: var(--sp-6)"
        :disabled="busy"
        @click="reconcile"
      >
        Reconcile with MT5
      </button>
    </section>

    <section v-else class="panel result empty-result">
      <div class="empty">
        <div class="icon">↑</div>
        <div class="title">No order submitted yet</div>
        <p class="muted">Fill the ticket and submit. The risk verdict and audit result appear here.</p>
      </div>
    </section>
  </div>

  <dialog ref="confirmDialog" class="modal" aria-labelledby="confirm-title" @click="onBackdrop" @cancel="closeConfirm">
    <h3 id="confirm-title">Confirm real-account order</h3>
    <p>Submitting a <strong>real-money</strong> order: <span class="mono">{{ form.side }} {{ form.volume }}</span> lots of <span class="mono">{{ form.symbol }}</span>.</p>
    <p class="muted" style="margin-top: var(--sp-4)">It still passes the Risk Manager, and in Phase 1 you must approve it before it reaches the broker.</p>
    <div class="row" style="justify-content: flex-end; margin-top: var(--sp-7); gap: var(--sp-4)">
      <button class="btn secondary" autofocus @click="closeConfirm">Cancel</button>
      <button class="btn danger" @click="doSubmit">Submit order</button>
    </div>
  </dialog>
</template>

<style scoped>
.order-layout { display: flex; flex-wrap: wrap; gap: var(--sp-6); align-items: flex-start; }
.ticket { flex: 1 1 380px; max-width: 460px; }
.result { flex: 1 1 320px; }
.empty-result { display: grid; place-items: center; min-height: 220px; }
</style>
