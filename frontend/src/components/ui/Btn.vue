<script setup lang="ts">
import Icon from "./Icon.vue";

withDefaults(
  defineProps<{
    variant?: "secondary" | "ghost" | "danger";
    sm?: boolean;
    full?: boolean;
    icon?: string;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
    title?: string;
    loading?: boolean;
  }>(),
  { type: "button" },
);
defineEmits<{ (e: "click", ev: MouseEvent): void }>();
</script>

<template>
  <button
    :type="type"
    :title="title"
    :disabled="disabled"
    class="btn"
    :class="[variant, { sm, full }]"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="spin" />
    <Icon v-else-if="icon" :name="icon" :size="sm ? 15 : 16" />
    <slot />
  </button>
</template>
