<script setup lang="ts">
// Inline label-left / switch-right row used in settings forms.
import Switch from "./Switch.vue";

defineProps<{ label: string; sub?: string; checked: boolean }>();
defineEmits<{ (e: "change", value: boolean): void }>();
</script>

<template>
  <div class="toggle-row">
    <div>
      <div class="tl">{{ label }}</div>
      <div v-if="sub" class="ts">{{ sub }}</div>
    </div>
    <Switch :checked="checked" @change="$emit('change', $event)" />
  </div>
</template>
