<script setup lang="ts">
import Icon from "./ui/Icon.vue";
import { ACCENTS, useTheme, type Density } from "../composables/useTheme";

const { accent, density, mono } = useTheme();
defineEmits<{ (e: "close"): void }>();
</script>

<template>
  <div class="tweaks">
    <div class="tweaks-head">
      <span class="t"><Icon name="sliders" :size="15" /> Tweaks</span>
      <span
        class="icon-btn"
        style="width: 28px; height: 28px; border: none; background: transparent"
        @click="$emit('close')"
      >
        <Icon name="x" :size="15" />
      </span>
    </div>
    <div class="tweaks-body">
      <div class="tweak-row">
        <span class="rl">Accent</span>
        <div class="swatches">
          <span
            v-for="a in ACCENTS"
            :key="a.name"
            class="swatch"
            :title="a.name"
            :data-on="accent === a.h"
            :style="{ background: `oklch(0.62 0.15 ${a.h})` }"
            @click="accent = a.h"
          />
        </div>
      </div>
      <div class="tweak-row">
        <span class="rl">Density</span>
        <div class="seg" style="width: 100%">
          <button
            v-for="d in (['compact', 'cozy'] as Density[])"
            :key="d"
            :data-on="density === d"
            @click="density = d"
          >
            {{ d === "compact" ? "Compact" : "Cozy" }}
          </button>
        </div>
      </div>
      <div class="tweak-row">
        <span class="rl">Number style</span>
        <div class="seg" style="width: 100%">
          <button :data-on="!mono" @click="mono = false">Sans</button>
          <button :data-on="mono" @click="mono = true">Mono</button>
        </div>
      </div>
    </div>
  </div>
</template>
