<script setup lang="ts">
defineProps<{
  tabs: Array<{ id: string; label: string; count?: number }>;
  active: string;
}>();
defineEmits<{ (e: "change", id: string): void }>();
</script>

<template>
  <div class="tabs" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.id"
      role="tab"
      class="tab"
      :data-on="active === t.id"
      @click="$emit('change', t.id)"
    >
      {{ t.label }}
      <span v-if="t.count != null" class="tab-count">{{ t.count }}</span>
    </button>
  </div>
</template>
