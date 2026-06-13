<script setup lang="ts">
import { computed } from "vue";
import type { Candle } from "../../api/client";

export interface ChartMarker {
  price: number;
  label: string;
  tone?: "pos" | "neg" | "accent";
}

const props = withDefaults(
  defineProps<{
    candles: Candle[];
    height?: number;
    d40?: number | null;
    d20?: number | null;
    showChannels?: boolean;
    markers?: ChartMarker[];
    livePrice?: number | null;
  }>(),
  { height: 380, d40: 40, d20: 20, showChannels: true, markers: () => [], livePrice: null },
);

const W = 1000;
const PAD_T = 14;
const PAD_B = 22;
const PAD_R = 8;

// Rolling Donchian channel (highest high / lowest low over the prior `period` bars).
function donchian(period: number) {
  const c = props.candles;
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < c.length; i++) {
    if (i < period - 1) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    let hi = -Infinity;
    let lo = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (c[j].high > hi) hi = c[j].high;
      if (c[j].low < lo) lo = c[j].low;
    }
    upper.push(hi);
    lower.push(lo);
  }
  return { upper, lower };
}

const ch40 = computed(() => (props.showChannels && props.d40 ? donchian(props.d40) : null));
const ch20 = computed(() => (props.showChannels && props.d20 ? donchian(props.d20) : null));

const bounds = computed(() => {
  const c = props.candles;
  if (!c.length) return { min: 0, max: 1 };
  let min = Infinity;
  let max = -Infinity;
  for (const bar of c) {
    if (bar.low < min) min = bar.low;
    if (bar.high > max) max = bar.high;
  }
  for (const m of props.markers) {
    if (m.price < min) min = m.price;
    if (m.price > max) max = m.price;
  }
  if (props.livePrice != null) {
    if (props.livePrice < min) min = props.livePrice;
    if (props.livePrice > max) max = props.livePrice;
  }
  const span = max - min || 1;
  return { min: min - span * 0.04, max: max + span * 0.04 };
});

function y(price: number) {
  const { min, max } = bounds.value;
  const span = max - min || 1;
  return +(PAD_T + (props.height - PAD_T - PAD_B) * (1 - (price - min) / span)).toFixed(2);
}
const slot = computed(() => (W - PAD_R) / (props.candles.length || 1));
function cx(i: number) {
  return +(i * slot.value + slot.value / 2).toFixed(2);
}
const bodyW = computed(() => Math.max(1, Math.min(slot.value * 0.66, 14)));

const candleViews = computed(() =>
  props.candles.map((c, i) => {
    const up = c.close >= c.open;
    const yo = y(c.open);
    const yc = y(c.close);
    return {
      key: i,
      x: cx(i),
      color: up ? "var(--pos)" : "var(--neg)",
      wickTop: y(c.high),
      wickBottom: y(c.low),
      bodyTop: Math.min(yo, yc),
      bodyH: Math.max(1, Math.abs(yc - yo)),
    };
  }),
);

function channelPath(values: (number | null)[]) {
  let d = "";
  let started = false;
  values.forEach((v, i) => {
    if (v == null) {
      started = false;
      return;
    }
    d += `${started ? " L" : " M"} ${cx(i)} ${y(v)}`;
    started = true;
  });
  return d.trim();
}

const gridLines = computed(() => {
  const { min, max } = bounds.value;
  return [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const price = max - (max - min) * f;
    return { y: y(price), price };
  });
});

const timeLabels = computed(() => {
  const c = props.candles;
  if (c.length < 2) return [];
  const idx = [0, Math.floor(c.length / 2), c.length - 1];
  return idx.map((i) => ({
    x: cx(i),
    text: new Date(c[i].time).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
  }));
});

function fmtPrice(p: number) {
  return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>

<template>
  <div style="position: relative; width: 100%">
    <svg :viewBox="`0 0 ${W} ${height}`" preserveAspectRatio="none" width="100%" :height="height" style="display: block; overflow: visible">
      <!-- price gridlines -->
      <line v-for="g in gridLines" :key="'g' + g.y" x1="0" :x2="W" :y1="g.y" :y2="g.y" stroke="var(--border)" stroke-width="1" stroke-dasharray="2 4" vector-effect="non-scaling-stroke" />

      <!-- Donchian D40 (entry channel) -->
      <template v-if="ch40">
        <path :d="channelPath(ch40.upper)" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="5 4" vector-effect="non-scaling-stroke" opacity="0.85" />
        <path :d="channelPath(ch40.lower)" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="5 4" vector-effect="non-scaling-stroke" opacity="0.85" />
      </template>
      <!-- Donchian D20 (exit channel) -->
      <template v-if="ch20">
        <path :d="channelPath(ch20.upper)" fill="none" stroke="var(--ink-faint)" stroke-width="1.2" vector-effect="non-scaling-stroke" opacity="0.6" />
        <path :d="channelPath(ch20.lower)" fill="none" stroke="var(--ink-faint)" stroke-width="1.2" vector-effect="non-scaling-stroke" opacity="0.6" />
      </template>

      <!-- candles -->
      <g v-for="c in candleViews" :key="c.key">
        <line :x1="c.x" :x2="c.x" :y1="c.wickTop" :y2="c.wickBottom" :stroke="c.color" stroke-width="1" vector-effect="non-scaling-stroke" />
        <rect :x="c.x - bodyW / 2" :y="c.bodyTop" :width="bodyW" :height="c.bodyH" :fill="c.color" />
      </g>

      <!-- entry/SL/TP markers -->
      <line
        v-for="(m, i) in markers"
        :key="'m' + i"
        x1="0"
        :x2="W"
        :y1="y(m.price)"
        :y2="y(m.price)"
        :stroke="`var(--${m.tone || 'accent'})`"
        stroke-width="1.4"
        stroke-dasharray="3 3"
        vector-effect="non-scaling-stroke"
      />

      <!-- live last price -->
      <line v-if="livePrice != null" x1="0" :x2="W" :y1="y(livePrice)" :y2="y(livePrice)" stroke="var(--accent-ink)" stroke-width="1.4" vector-effect="non-scaling-stroke" />
    </svg>

    <!-- price axis labels (absolutely positioned, crisp text outside the scaled SVG) -->
    <div class="axis-y">
      <span v-for="g in gridLines" :key="'l' + g.y" class="mono" :style="{ top: g.y + 'px' }">{{ fmtPrice(g.price) }}</span>
    </div>
    <!-- marker labels -->
    <div class="markers">
      <span v-for="(m, i) in markers" :key="'ml' + i" class="mono marker-tag" :class="m.tone || 'accent'" :style="{ top: y(m.price) + 'px' }">{{ m.label }} {{ fmtPrice(m.price) }}</span>
      <span v-if="livePrice != null" class="mono marker-tag live" :style="{ top: y(livePrice) + 'px' }">{{ fmtPrice(livePrice) }}</span>
    </div>
    <div class="axis-x">
      <span v-for="(t, i) in timeLabels" :key="i" class="faint" :style="{ left: (t.x / W * 100) + '%' }">{{ t.text }}</span>
    </div>
  </div>
</template>

<style scoped>
.axis-y { position: absolute; inset: 0; pointer-events: none; }
.axis-y span {
  position: absolute; left: 2px; transform: translateY(-50%);
  font-size: var(--text-xs); color: var(--ink-faint); white-space: nowrap;
  background: color-mix(in oklch, var(--surface) 75%, transparent);
  padding: 0 3px; border-radius: 3px;
}
.markers { position: absolute; inset: 0; pointer-events: none; }
.marker-tag {
  position: absolute; right: 2px; transform: translateY(-50%);
  font-size: var(--text-xs); font-weight: 600; padding: 1px 6px; border-radius: var(--r-sm);
  white-space: nowrap;
}
.marker-tag.pos { background: var(--allow-bg); color: var(--allow-fg); }
.marker-tag.neg { background: var(--block-bg); color: var(--block-fg); }
.marker-tag.accent { background: var(--accent-soft); color: var(--accent-ink); }
.marker-tag.live { background: var(--accent-ink); color: var(--surface); }
.axis-x { position: relative; height: 16px; margin-top: 2px; }
.axis-x span { position: absolute; transform: translateX(-50%); font-size: var(--text-xs); color: var(--ink-faint); white-space: nowrap; }
.axis-x span:first-child { transform: none; }
.axis-x span:last-child { transform: translateX(-100%); }
</style>
