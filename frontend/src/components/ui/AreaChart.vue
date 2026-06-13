<script setup lang="ts">
import { computed } from "vue";
import { points, smoothPath, linePath, uid } from "./chart";

const props = withDefaults(
  defineProps<{
    data: number[];
    height?: number;
    color?: string;
    smooth?: boolean;
    axisLabels?: string[];
  }>(),
  { height: 130, color: "var(--accent)", smooth: true },
);

const W = 600;
const PAD = 8;
const id = uid("ac");

const pts = computed(() => points(props.data, W, props.height, PAD));
const line = computed(() => (props.smooth ? smoothPath(pts.value) : linePath(pts.value)));
const area = computed(() => {
  const p = pts.value;
  if (!p.length) return "";
  return `${line.value} L ${p[p.length - 1][0]} ${props.height} L ${p[0][0]} ${props.height} Z`;
});
const last = computed(() => pts.value[pts.value.length - 1] ?? [0, 0]);
const grids = [0.25, 0.5, 0.75];
</script>

<template>
  <div style="position: relative; width: 100%">
    <svg
      :viewBox="`0 0 ${W} ${height}`"
      preserveAspectRatio="none"
      width="100%"
      :height="height"
      style="display: block; overflow: visible"
    >
      <defs>
        <linearGradient :id="id" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.22" />
          <stop offset="100%" :stop-color="color" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line
        v-for="g in grids"
        :key="g"
        x1="0"
        :x2="W"
        :y1="height * g"
        :y2="height * g"
        stroke="var(--border)"
        stroke-width="1"
        stroke-dasharray="2 4"
        vector-effect="non-scaling-stroke"
      />
      <path :d="area" :fill="`url(#${id})`" />
      <path
        :d="line"
        fill="none"
        :stroke="color"
        stroke-width="2"
        vector-effect="non-scaling-stroke"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
      <circle :cx="last[0]" :cy="last[1]" r="3.5" :fill="color" vector-effect="non-scaling-stroke" />
    </svg>
    <div v-if="axisLabels" class="row between" style="margin-top: 6px">
      <span v-for="(l, i) in axisLabels" :key="i" class="faint" style="font-size: var(--text-xs)">{{ l }}</span>
    </div>
  </div>
</template>
