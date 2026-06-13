<script setup lang="ts">
import { computed, useSlots } from "vue";
import { badgeClass, type BadgeTone } from "./badge";

const props = withDefaults(
  defineProps<{ tone?: BadgeTone | "auto"; lg?: boolean; noDot?: boolean }>(),
  { tone: "auto", noDot: false, lg: false },
);
const slots = useSlots();

function slotText(): string {
  const nodes = slots.default?.() ?? [];
  return nodes.map((n) => (typeof n.children === "string" ? n.children : "")).join("");
}

const cls = computed(() => {
  if (props.tone === "accent") return "accent";
  if (props.tone && props.tone !== "auto") return props.tone;
  return badgeClass(slotText());
});
</script>

<template>
  <span class="badge" :class="[cls, { lg, 'no-dot': noDot }]"><slot /></span>
</template>
