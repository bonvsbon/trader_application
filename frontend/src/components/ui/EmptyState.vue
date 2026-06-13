<script setup lang="ts">
import Icon from "./Icon.vue";

withDefaults(
  defineProps<{ icon?: string; title: string; desc?: string }>(),
  { icon: "diamond" },
);
</script>

<template>
  <div class="empty">
    <Icon class="ei" :name="icon" :size="30" :stroke="1.6" />
    <div class="et">{{ title }}</div>
    <div v-if="desc" class="ed">{{ desc }}</div>
  </div>
</template>
