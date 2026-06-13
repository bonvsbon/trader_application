<script setup lang="ts">
import { useSlots } from "vue";

withDefaults(
  defineProps<{ title?: string; pad?: boolean; tight?: boolean }>(),
  { pad: true, tight: false },
);
const slots = useSlots();
</script>

<template>
  <section class="panel">
    <div v-if="title || slots.action" class="panel-head">
      <span class="panel-title">{{ title }}</span>
      <slot name="action" />
    </div>
    <div v-if="pad" :class="tight ? 'pad-tight' : 'panel-pad'"><slot /></div>
    <slot v-else />
  </section>
</template>
