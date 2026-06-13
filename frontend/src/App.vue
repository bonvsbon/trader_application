<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import IntervalCountdown from "./components/IntervalCountdown.vue";
import TweaksPanel from "./components/TweaksPanel.vue";
import Icon from "./components/ui/Icon.vue";
import Badge from "./components/ui/Badge.vue";
import { badgeClass } from "./components/ui/badge";
import { useTheme } from "./composables/useTheme";
import { api } from "./api/client";
import { useAuthStore } from "./stores/auth";

const { theme, toggle } = useTheme();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const publicPage = computed(() => Boolean(route.meta.public));
const tweaksOpen = ref(false);

const NAV = [
  {
    group: "Trading",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
      { to: "/order", label: "Manual Order", icon: "order" },
      { to: "/strategy", label: "Strategy", icon: "strategy" },
      { to: "/approvals", label: "Approvals", icon: "approvals" },
    ],
  },
  {
    group: "Monitoring",
    items: [
      { to: "/chart", label: "Chart", icon: "market" },
      { to: "/risk", label: "Risk Monitor", icon: "risk" },
      { to: "/history", label: "History", icon: "history" },
      { to: "/analysis", label: "AI Analysis", icon: "analysis" },
      { to: "/logs", label: "Logs", icon: "logs" },
    ],
  },
];
const SETTINGS = [
  { to: "/account", label: "MT5 Account", icon: "account" },
  { to: "/settings/providers", label: "Providers", icon: "providers" },
  { to: "/settings/market-data", label: "Market Data", icon: "market" },
];

// Lightweight global safety status for the top strip (mode / bridge / kill switch).
const status = ref<any>(null);
const online = ref(true);
let timer: number | undefined;

async function loadStatus() {
  if (publicPage.value || (auth.enabled && !auth.authenticated)) return;
  try {
    status.value = await api.dashboard();
    online.value = true;
  } catch {
    online.value = false;
  }
}

async function logout() {
  await auth.logout();
  await router.replace("/login");
}

onMounted(() => {
  loadStatus();
  // The safety-strip status runs a full risk preview, which over the live EA
  // bridge is several serialized RPCs (~5s). Poll gently so it never saturates
  // the single EA socket that the chart/watchlist/account also share.
  timer = window.setInterval(loadStatus, 20000);
});
onUnmounted(() => timer && clearInterval(timer));
</script>

<template>
  <router-view v-if="publicPage" />
  <div v-else class="app">
    <aside class="sidebar">
      <div class="brand">
        <span class="mark"><span>◇</span></span>
        <div class="col" style="gap: 0">
          <span class="word">ทางรอด</span>
          <span class="sub">Thang Rod · MT5</span>
        </div>
      </div>

      <nav class="nav-scroll">
        <div v-for="g in NAV" :key="g.group" class="nav-group">
          <span class="nav-label">{{ g.group }}</span>
          <router-link
            v-for="it in g.items"
            :key="it.to"
            :to="it.to"
            custom
            v-slot="{ isActive, navigate }"
          >
            <a class="nav-link" :data-active="isActive" @click="navigate">
              <Icon :name="it.icon" :size="18" /><span class="txt">{{ it.label }}</span>
            </a>
          </router-link>
        </div>
      </nav>

      <div class="nav-group">
        <span class="nav-label">Settings</span>
        <router-link
          v-for="it in SETTINGS"
          :key="it.to"
          :to="it.to"
          custom
          v-slot="{ isActive, navigate }"
        >
          <a class="nav-link" :data-active="isActive" @click="navigate">
            <Icon :name="it.icon" :size="18" /><span class="txt">{{ it.label }}</span>
          </a>
        </router-link>
      </div>

      <div class="sidebar-foot"><IntervalCountdown /></div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div v-if="online && status" class="safety-strip">
          <div class="strip-item">
            <span class="lbl">Account</span>
            <Badge :tone="status.account.account_type === 'DEMO' ? 'allow' : 'block'">{{ status.account.account_type }}</Badge>
          </div>
          <div class="strip-sep" />
          <div class="strip-item">
            <span class="lbl">Mode</span>
            <Badge tone="accent" no-dot>{{ status.trading_mode }}</Badge>
          </div>
          <div class="strip-sep" />
          <div class="strip-item">
            <span class="lbl">Bridge</span>
            <Badge :tone="badgeClass(status.bridge_health)">{{ status.bridge_health }}</Badge>
          </div>
          <template v-if="status.safety_flags.emergency_stop">
            <div class="strip-sep" />
            <Badge tone="block">EMERGENCY STOP</Badge>
          </template>
          <template v-if="status.safety_flags.auto_real_full_enabled">
            <div class="strip-sep" />
            <Badge tone="block">AUTO-REAL LIVE</Badge>
          </template>
        </div>
        <div v-else class="safety-strip">
          <Badge tone="block">Backend offline</Badge>
        </div>

        <div class="row" style="gap: var(--sp-4)">
          <div v-if="auth.user" class="user-chip">
            <span class="mono">{{ auth.user.mt5_login }}</span>
            <span class="muted">{{ auth.user.mt5_account.server }}</span>
            <button class="btn ghost sm" @click="logout">Sign out</button>
          </div>
          <span class="icon-btn" :data-on="tweaksOpen" title="Tweaks" @click="tweaksOpen = !tweaksOpen">
            <Icon name="sliders" :size="17" />
          </span>
          <span class="icon-btn" title="Toggle theme" @click="toggle">
            <Icon :name="theme === 'dark' ? 'sun' : 'moon'" :size="17" />
          </span>
        </div>
      </header>

      <main class="content">
        <div class="content-inner">
          <div class="screen" :key="route.path"><router-view /></div>
        </div>
      </main>
    </div>

    <TweaksPanel v-if="tweaksOpen" @close="tweaksOpen = false" />
    <span v-else class="fab" title="Tweaks" @click="tweaksOpen = true"><Icon name="sliders" :size="18" /></span>
  </div>
</template>

<style scoped>
.user-chip {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  font-size: var(--text-sm);
  padding-right: var(--sp-3);
}
</style>
