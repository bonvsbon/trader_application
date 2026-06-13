<script setup lang="ts">
import { computed } from "vue";
import Icon from "./Icon.vue";
import Reasons from "./Reasons.vue";
import { badgeClass } from "./badge";

const props = withDefaults(
  defineProps<{
    verdict: string;
    headline?: string;
    reasons?: string[];
    warnings?: string[];
    symbol?: string;
    compact?: boolean;
  }>(),
  { headline: "Trade readiness", reasons: () => [], warnings: () => [] },
);

const VERDICT_LABEL: Record<string, string> = {
  ALLOW: "Cleared to trade",
  WARN: "Trade with caution",
  BLOCK: "Trading blocked",
};

const tone = computed(() => badgeClass(props.verdict) || "block");
const isBlock = computed(() => props.verdict === "BLOCK");
const list = computed(() => (isBlock.value ? props.reasons : props.warnings));
const iconName = computed(() =>
  props.verdict === "BLOCK" ? "x" : props.verdict === "WARN" ? "alert" : "check",
);
</script>

<template>
  <section
    class="panel verdict"
    :class="tone"
    :style="{
      borderColor: `var(--${tone}-fg)`,
      boxShadow: `inset 3px 0 0 var(--${tone}-fg), var(--shadow-sm)`,
    }"
  >
    <div
      class="panel-pad verdict-body"
      :style="{ gridTemplateColumns: compact ? '1fr' : 'auto 1fr' }"
    >
      <div class="col" style="gap: var(--sp-4); min-width: 220px">
        <span class="panel-title" :style="{ color: `var(--${tone}-fg)` }">
          {{ headline }}<template v-if="symbol"> · {{ symbol }}</template>
        </span>
        <div class="row" style="gap: var(--sp-5)">
          <Icon :name="iconName" :size="30" :stroke="2.4" :style="{ color: `var(--${tone}-fg)` }" />
          <span class="verdict-word" :style="{ color: `var(--${tone}-fg)` }">{{ verdict }}</span>
        </div>
        <span class="muted" style="font-size: var(--text-sm)">{{ VERDICT_LABEL[verdict] }}</span>
      </div>
      <div :style="{ borderLeft: compact ? 'none' : '1px solid var(--border)', paddingLeft: compact ? 0 : 'var(--sp-8)' }">
        <template v-if="list.length">
          <div class="panel-title" style="margin-bottom: var(--sp-4)">
            {{ isBlock ? "Why blocked" : "Warnings" }}
          </div>
          <Reasons :items="list" :warn="!isBlock" />
        </template>
        <div v-else class="row" style="color: var(--allow-fg)">
          <Icon name="check" :size="16" />
          <span style="font-size: var(--text-sm)">All risk checks passed. No active warnings.</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.verdict-body {
  display: grid;
  gap: var(--sp-8);
  align-items: center;
}
.verdict-word {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: var(--text-3xl);
  letter-spacing: -0.02em;
}
@media (max-width: 720px) {
  .verdict-body {
    grid-template-columns: 1fr !important;
  }
}
</style>
