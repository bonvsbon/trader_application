<script setup lang="ts">
import Sparkline from "./Sparkline.vue";

defineProps<{
  label: string;
  value: string | number;
  sub?: string;
  tone?: string;
  spark?: number[];
  sparkColor?: string;
}>();
</script>

<template>
  <div class="panel" style="padding: calc(var(--sp-6) * var(--density)); display: flex; flex-direction: column; gap: var(--sp-3)">
    <span class="faint" style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600">{{ label }}</span>
    <span class="mono" style="font-size: var(--text-xl); font-weight: 700; letter-spacing: -0.01em" :style="{ color: tone ? `var(--${tone})` : 'var(--ink)' }">{{ value }}</span>
    <Sparkline v-if="spark" :data="spark" :width="120" :height="26" :color="sparkColor || 'var(--ink-faint)'" />
    <span v-else-if="sub" class="faint" style="font-size: var(--text-xs)">{{ sub }}</span>
  </div>
</template>
