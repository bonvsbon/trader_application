<script setup lang="ts">
import { useSlots } from "vue";

defineProps<{ title: string; sub?: string }>();
const slots = useSlots();
</script>

<template>
  <header class="page-head">
    <div class="col" style="gap: 4px">
      <h1 style="font-size: var(--text-2xl)">{{ title }}</h1>
      <span v-if="sub" class="muted" style="font-size: var(--text-sm)">{{ sub }}</span>
    </div>
    <div v-if="slots.actions" class="row wrap" style="gap: var(--sp-4)">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-6);
  margin-bottom: var(--sp-8);
  flex-wrap: wrap;
}
</style>
