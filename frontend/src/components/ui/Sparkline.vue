<script setup lang="ts">
import { computed } from "vue";
import { points, linePath } from "./chart";

const props = withDefaults(
  defineProps<{ data: number[]; width?: number; height?: number; color?: string; strokeWidth?: number }>(),
  { width: 72, height: 22, color: "var(--ink-muted)", strokeWidth: 1.6 },
);

const pts = computed(() => points(props.data, props.width, props.height, 3));
const line = computed(() => linePath(pts.value));
const last = computed(() => pts.value[pts.value.length - 1] ?? [0, 0]);
const ok = computed(() => props.data && props.data.length >= 2);
</script>

<template>
  <svg v-if="ok" :width="width" :height="height" style="display: block; overflow: visible">
    <path :d="line" fill="none" :stroke="color" :stroke-width="strokeWidth" stroke-linejoin="round" stroke-linecap="round" />
    <circle :cx="last[0]" :cy="last[1]" r="1.8" :fill="color" />
  </svg>
</template>
