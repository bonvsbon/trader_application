<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { api } from "../api/client";

interface Status {
  running: boolean;
  current_step: string;
  last_run: string | null;
  next_run: string | null;
  countdown_seconds: number | null;
  interval_seconds: number | null;
  next_delay_seconds: number | null;
  consecutive_failures: number;
  last_error: string | null;
}

const status = ref<Status>({
  running: false, current_step: "idle", last_run: null, next_run: null,
  countdown_seconds: null, interval_seconds: null, next_delay_seconds: null,
  consecutive_failures: 0, last_error: null,
});
const busy = ref(false);
const actionError = ref<string | null>(null);

let ws: WebSocket | null = null;
let pollTimer: number | undefined;

function apply(s: Status) {
  status.value = s;
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = window.setInterval(async () => {
    try { apply(await api.workflowStatus()); } catch { /* backend down */ }
  }, 2000);
}

function connect() {
  try {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/status`);
    ws.onmessage = (e) => apply(JSON.parse(e.data));
    ws.onclose = () => { ws = null; startPolling(); };
    ws.onerror = () => { ws?.close(); };
  } catch {
    startPolling();
  }
}

const countdown = computed(() => {
  const s = status.value.countdown_seconds;
  if (s === null || s === undefined) return "––:––";
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
});

function errorText(value: any) {
  return value?.response?.data?.detail ?? value?.message ?? "Backend request failed";
}

async function start() {
  busy.value = true;
  actionError.value = null;
  try { apply(await api.workflowStart()); }
  catch (error: any) { actionError.value = errorText(error); }
  finally { busy.value = false; }
}
async function stop() {
  busy.value = true;
  actionError.value = null;
  try { apply(await api.workflowStop()); }
  catch (error: any) { actionError.value = errorText(error); }
  finally { busy.value = false; }
}
async function runNow() {
  busy.value = true;
  actionError.value = null;
  try { apply((await api.workflowRun()).status); }
  catch (error: any) { actionError.value = errorText(error); }
  finally { busy.value = false; }
}

onMounted(connect);
onUnmounted(() => { ws?.close(); if (pollTimer) clearInterval(pollTimer); });
</script>

<template>
  <section class="countdown panel pad-tight" aria-label="Interval workflow">
    <div class="row between">
      <span class="panel-title">Workflow</span>
      <span class="run-state" :class="{ on: status.running }">
        <span class="dot"></span>{{ status.running ? "Running" : "Stopped" }}
      </span>
    </div>

    <div class="time mono">{{ countdown }}</div>
    <div class="step faint">{{ status.running ? status.current_step : "Idle" }}</div>
    <p v-if="status.consecutive_failures > 0" class="backoff">
      Backing off after {{ status.consecutive_failures }} failed
      {{ status.consecutive_failures === 1 ? "cycle" : "cycles" }}
      <span v-if="status.next_delay_seconds">· retry in {{ status.next_delay_seconds }}s</span>
    </p>

    <div class="row" style="margin-top: var(--sp-5); gap: var(--sp-3)">
      <button v-if="!status.running" class="btn sm" :disabled="busy" @click="start" style="flex: 1">Start</button>
      <button v-else class="btn sm danger" :disabled="busy" @click="stop" style="flex: 1">Stop</button>
      <button class="btn sm secondary" :disabled="busy" @click="runNow">Run now</button>
    </div>

    <p v-if="status.last_error" class="err">{{ status.last_error }}</p>
    <p v-if="actionError" class="err">{{ actionError }}</p>
  </section>
</template>

<style scoped>
.countdown { display: flex; flex-direction: column; }
.run-state { display: inline-flex; align-items: center; gap: 6px; font-size: var(--text-xs); color: var(--ink-muted); }
.run-state .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-faint); }
.run-state.on { color: var(--allow-fg); }
.run-state.on .dot { background: var(--allow-fg); box-shadow: 0 0 0 3px var(--allow-bg); }
.time { font-size: 2rem; font-weight: 600; letter-spacing: 0.02em; text-align: center; margin: var(--sp-5) 0 2px; }
.step { text-align: center; font-size: var(--text-xs); text-transform: capitalize; }
.backoff { margin-top: var(--sp-3); text-align: center; font-size: var(--text-xs); color: var(--warn-fg); }
.err { margin-top: var(--sp-4); font-size: var(--text-xs); color: var(--block-fg); }
</style>
