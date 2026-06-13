<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{ data: Array<{ v: number; label?: string }>; height?: number; gap?: number }>(),
  { height: 44, gap: 3 },
);

const max = computed(() => Math.max(...props.data.map((d) => Math.abs(d.v)), 1));
function barHeight(v: number) {
  return Math.max(2, (Math.abs(v) / max.value) * (props.height / 2 - 2));
}
</script>

<template>
  <div class="row" :style="{ alignItems: 'stretch', gap: gap + 'px', height: height + 'px' }">
    <div
      v-for="(d, i) in data"
      :key="i"
      :title="d.label"
      style="flex: 1; display: flex; flex-direction: column; justify-content: center; min-width: 0"
    >
      <div :style="{ height: height / 2 + 'px', display: 'flex', alignItems: 'flex-end' }">
        <span
          v-if="d.v >= 0"
          :style="{ width: '100%', height: barHeight(d.v) + 'px', background: 'var(--pos)', borderRadius: '3px 3px 0 0', opacity: 0.85 }"
        />
      </div>
      <div :style="{ height: height / 2 + 'px', display: 'flex', alignItems: 'flex-start' }">
        <span
          v-if="d.v < 0"
          :style="{ width: '100%', height: barHeight(d.v) + 'px', background: 'var(--neg)', borderRadius: '0 0 3px 3px', opacity: 0.85 }"
        />
      </div>
    </div>
  </div>
</template>
