<script setup lang="ts">
// Key/value row. Value can be passed as text via `v` prop or via the default slot.
defineProps<{ k: string; v?: string | number; mono?: boolean; tone?: string; sub?: string }>();
</script>

<template>
  <div class="kv">
    <span class="k">{{ k }}</span>
    <span class="v" :class="[{ mono }, tone]">
      <slot>{{ v }}</slot>
      <span v-if="sub" class="faint" style="font-weight: 400; font-size: var(--text-xs); margin-left: 6px">{{ sub }}</span>
    </span>
  </div>
</template>
