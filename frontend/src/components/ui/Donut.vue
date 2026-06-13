<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    value: number;
    size?: number;
    stroke?: number;
    color?: string;
    track?: string;
    label?: string;
    sub?: string;
  }>(),
  { size: 92, stroke: 9, color: "var(--allow-fg)", track: "var(--neutral-bg)" },
);

const r = computed(() => (props.size - props.stroke) / 2);
const c = computed(() => 2 * Math.PI * r.value);
const off = computed(() => c.value * (1 - props.value / 100));
</script>

<template>
  <div :style="{ position: 'relative', width: size + 'px', height: size + 'px', flex: 'none' }">
    <svg :width="size" :height="size" style="transform: rotate(-90deg)">
      <circle :cx="size / 2" :cy="size / 2" :r="r" fill="none" :stroke="track" :stroke-width="stroke" />
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="r"
        fill="none"
        :stroke="color"
        :stroke-width="stroke"
        :stroke-dasharray="c"
        :stroke-dashoffset="off"
        stroke-linecap="round"
        style="transition: stroke-dashoffset 0.6s var(--ease)"
      />
    </svg>
    <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center">
      <span class="mono" style="font-size: var(--text-lg); font-weight: 700; line-height: 1">{{ label }}</span>
      <span v-if="sub" class="faint" style="font-size: var(--text-xs)">{{ sub }}</span>
    </div>
  </div>
</template>
