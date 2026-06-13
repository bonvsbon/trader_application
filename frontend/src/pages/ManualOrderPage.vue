<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { api, type OrderResult, type OrderTicket, type RiskPreview } from "../api/client";
import PageHead from "../components/ui/PageHead.vue";
import Panel from "../components/ui/Panel.vue";
import Badge from "../components/ui/Badge.vue";
import Btn from "../components/ui/Btn.vue";
import Kv from "../components/ui/Kv.vue";
import Field from "../components/ui/Field.vue";
import Switch from "../components/ui/Switch.vue";
import Notice from "../components/ui/Notice.vue";
import Reasons from "../components/ui/Reasons.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import Icon from "../components/ui/Icon.vue";
import { badgeClass } from "../components/ui/badge";

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
  result.value = null;
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
  if (isReal.value) confirmDialog.value?.showModal();
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

function money(v: number | null | undefined, sign = "") {
  return v == null ? "—" : `${sign}$${Math.abs(v).toFixed(2)}`;
}
function pct(v: number | null | undefined) {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}

onMounted(loadAccount);
</script>

<template>
  <PageHead title="Manual Order" sub="Every ticket runs through the Risk Manager before any broker call" />

  <div class="order-layout">
    <Panel title="Order ticket">
      <template #action><Badge :tone="accountType === 'DEMO' ? 'allow' : accountType === 'REAL' ? 'block' : ''">{{ accountType }}</Badge></template>
      <div class="stack">
        <Field label="Symbol"><input v-model="form.symbol" class="mono" /></Field>
        <Field label="Side">
          <div class="seg" :class="form.side === 'BUY' ? 'buy' : 'sell'">
            <button :data-on="form.side === 'BUY'" @click="form.side = 'BUY'">BUY</button>
            <button :data-on="form.side === 'SELL'" @click="form.side = 'SELL'">SELL</button>
          </div>
        </Field>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-5)">
          <Field label="Volume (lots)"><input class="mono" type="number" step="0.01" min="0.01" v-model.number="form.volume" /></Field>
          <Field label="Risk %"><input class="mono" type="number" step="0.1" min="0.1" v-model.number="form.risk_pct" /></Field>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-5)">
          <Field label="Stop loss" req><input class="mono" type="number" step="0.01" v-model.number="form.sl" placeholder="required" /></Field>
          <Field label="Take profit"><input class="mono" type="number" step="0.01" v-model.number="form.tp" placeholder="optional" /></Field>
        </div>
        <Notice v-if="previewError">{{ previewError }}</Notice>
        <div class="row" style="gap: var(--sp-4)">
          <Btn variant="secondary" icon="search" :disabled="busy" @click="checkPreview">Check size and risk</Btn>
          <Btn full :icon="isReal ? 'shield' : 'check'" :variant="isReal ? 'danger' : undefined" :loading="busy" @click="onSubmit">
            {{ isReal ? "Review real-account order" : "Submit order" }}
          </Btn>
        </div>
        <span class="hint">{{ isReal ? "Real: confirm → queued → approved before fill." : "Demo: fills immediately if the Risk Manager allows." }}</span>
      </div>
    </Panel>

    <div class="stack">
      <Panel title="Risk preview">
        <template #action><Badge v-if="preview" :tone="badgeClass(preview.decision)" lg>{{ preview.decision }}</Badge></template>
        <div v-if="preview" class="stack-sm">
          <Kv k="Entry (est.)" :v="preview.sizing.entry_price ?? '—'" mono />
          <Kv k="Estimated loss" :v="money(preview.sizing.estimated_loss)" mono tone="neg" />
          <Kv k="Estimated reward" :v="money(preview.sizing.estimated_reward, '+')" mono tone="pos" />
          <Kv k="Actual risk" :v="pct(preview.sizing.sized_risk_pct)" mono />
          <Kv k="Max lot for risk" :v="preview.sizing.max_volume_for_risk ?? '—'" mono />
          <Kv k="Projected portfolio risk" :v="pct(preview.sizing.projected_portfolio_risk_pct)" mono />
          <Reasons v-if="preview.reasons.length" :items="preview.reasons" />
          <div v-if="preview.warnings.length" style="margin-top: var(--sp-4)"><Notice tone="warn">{{ preview.warnings[0] }}</Notice></div>
        </div>
        <EmptyState v-else icon="search" title="No preview yet" desc="Fill the ticket and run Check size and risk." />
      </Panel>

      <Panel title="Result">
        <div v-if="result" class="stack-sm">
          <div class="row wrap" style="gap: var(--sp-4)">
            <Badge :tone="badgeClass(result.decision)" lg>{{ result.decision }}</Badge>
            <Badge :tone="badgeClass(result.state)">{{ result.state }}</Badge>
          </div>
          <p class="muted" style="margin: 0; font-size: var(--text-sm)">{{ result.message }}</p>
          <Reasons v-if="result.reasons?.length" :items="result.reasons" />
          <Reasons v-if="result.warnings?.length" :items="result.warnings" warn />
          <div v-if="result.state === 'PENDING_APPROVAL'" class="row" style="gap: var(--sp-4); margin-top: var(--sp-3)">
            <Btn sm icon="check" :disabled="busy" @click="approve">Approve and execute</Btn>
            <Btn sm variant="danger" icon="x" :disabled="busy" @click="reject">Reject order</Btn>
          </div>
          <Btn
            v-if="result.state === 'RECONCILIATION_REQUIRED' || result.state === 'SUBMITTED'"
            sm variant="secondary" icon="refresh" style="margin-top: var(--sp-3)" :disabled="busy" @click="reconcile"
          >Reconcile with MT5</Btn>
        </div>
        <EmptyState v-else icon="order" title="No order submitted yet" desc="Submitted tickets and their risk verdict appear here." />
      </Panel>
    </div>
  </div>

  <dialog ref="confirmDialog" class="modal" aria-labelledby="confirm-title" @click="onBackdrop" @cancel="closeConfirm">
    <div class="modal-card">
      <div class="row" style="gap: var(--sp-5); margin-bottom: var(--sp-5)">
        <span class="modal-ic"><Icon name="alert" :size="20" /></span>
        <h3 id="confirm-title" style="font-size: var(--text-lg)">Confirm real-account order</h3>
      </div>
      <p class="muted" style="font-size: var(--text-sm); line-height: 1.55">
        This sends a <strong style="color: var(--block-fg)">REAL</strong> {{ form.side }} order on {{ form.symbol }}, {{ form.volume }} lots. It will <strong>not</strong> fill immediately — it enters the approval queue and still requires a second manual approval.
      </p>
      <div class="row" style="gap: var(--sp-4); justify-content: flex-end; margin-top: var(--sp-7)">
        <Btn variant="secondary" @click="closeConfirm">Cancel</Btn>
        <Btn variant="danger" icon="shield" @click="doSubmit">Queue for approval</Btn>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.order-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.95fr);
  gap: var(--sp-7);
  align-items: start;
}
@media (max-width: 880px) {
  .order-layout { grid-template-columns: 1fr; }
}
</style>
