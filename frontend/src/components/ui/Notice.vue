<script setup lang="ts">
import { computed } from "vue";
import Icon from "./Icon.vue";

const props = withDefaults(
  defineProps<{ tone?: "block" | "warn" | "success" | "neutral" }>(),
  { tone: "block" },
);

const iconName = computed(
  () => ({ block: "alert", warn: "alert", success: "check", neutral: "info" })[props.tone],
);
</script>

<template>
  <div class="notice" :class="tone === 'block' ? '' : tone">
    <Icon class="ni" :name="iconName" :size="16" />
    <div><slot /></div>
  </div>
</template>
