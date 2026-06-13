<script setup lang="ts">
import Badge from "./ui/Badge.vue";

type NewsEvent = {
  title: string;
  currency: string;
  impact: string;
  starts_at: string;
  minutes_until: number;
  within_block_window: boolean;
  source: string;
};

defineProps<{
  events: NewsEvent[];
  emptyText?: string;
}>();

const thaiTime = new Intl.DateTimeFormat("th-TH", {
  timeZone: "Asia/Bangkok",
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function whenLabel(event: NewsEvent) {
  const minutes = event.minutes_until;
  if (minutes < 0) return `ผ่านมา ${Math.abs(Math.round(minutes))} นาที`;
  if (minutes < 60) return `อีก ${Math.round(minutes)} นาที`;
  if (minutes < 1440) return `อีก ${(minutes / 60).toFixed(1)} ชม.`;
  return `อีก ${Math.ceil(minutes / 1440)} วัน`;
}

function sourceLabel(source: string) {
  return source === "federal_reserve" ? "Federal Reserve" : "New York Fed";
}
</script>

<template>
  <div v-if="events?.length" class="news-list">
    <article
      v-for="event in events"
      :key="`${event.source}-${event.starts_at}-${event.title}`"
      class="news-event"
      :class="{ near: event.within_block_window }"
    >
      <div class="news-time">
        <span class="mono">{{ thaiTime.format(new Date(event.starts_at)) }}</span>
        <span class="faint">{{ whenLabel(event) }}</span>
      </div>
      <div class="news-copy">
        <strong>{{ event.title }}</strong>
        <span class="faint">{{ sourceLabel(event.source) }}</span>
      </div>
      <Badge :tone="event.within_block_window ? 'block' : 'accent'" no-dot>
        {{ event.currency }} · {{ event.impact }}
      </Badge>
    </article>
  </div>
  <div v-else class="faint empty-news">
    {{ emptyText || "ไม่พบข่าวแรงที่กำลังจะมาถึง" }}
  </div>
</template>

<style scoped>
.news-list { display: grid; }
.news-event {
  display: grid;
  grid-template-columns: minmax(138px, 0.8fr) minmax(220px, 2fr) auto;
  gap: var(--sp-6);
  align-items: center;
  padding: var(--sp-5) 0;
  border-bottom: 1px solid var(--border);
}
.news-event:last-child { border-bottom: 0; }
.news-event.near {
  margin: 0 calc(var(--sp-4) * -1);
  padding-inline: var(--sp-4);
  border-radius: var(--radius-md);
  background: var(--block-bg);
}
.news-time, .news-copy { display: flex; flex-direction: column; gap: 3px; }
.news-time { font-size: var(--text-sm); }
.news-copy strong { font-size: var(--text-sm); }
.news-copy span, .news-time span:last-child { font-size: var(--text-xs); }
.empty-news { padding: var(--sp-4) 0; font-size: var(--text-sm); }
@media (max-width: 720px) {
  .news-event { grid-template-columns: 1fr auto; }
  .news-copy { grid-column: 1 / -1; grid-row: 2; }
}
</style>
