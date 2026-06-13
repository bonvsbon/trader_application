<script setup lang="ts">
defineProps<{ checked: boolean; id?: string }>();
defineEmits<{ (e: "change", value: boolean): void }>();
</script>

<template>
  <label class="switch" :for="id">
    <input
      :id="id"
      type="checkbox"
      :checked="checked"
      @change="$emit('change', ($event.target as HTMLInputElement).checked)"
    />
    <span class="track" />
  </label>
</template>
