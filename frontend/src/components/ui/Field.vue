<script setup lang="ts">
defineProps<{ label?: string; hint?: string; req?: boolean }>();
</script>

<template>
  <div class="field">
    <label v-if="label">
      {{ label }}<span v-if="req" style="color: var(--block-fg); margin-left: 4px">*</span>
    </label>
    <slot />
    <span v-if="hint" class="hint">{{ hint }}</span>
  </div>
</template>
