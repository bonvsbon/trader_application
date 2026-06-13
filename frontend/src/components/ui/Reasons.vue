<script setup lang="ts">
defineProps<{ items?: string[]; warn?: boolean }>();
</script>

<template>
  <ul v-if="items && items.length" class="reasons" :class="{ warn }">
    <li v-for="(r, i) in items" :key="i">{{ r }}</li>
  </ul>
</template>
