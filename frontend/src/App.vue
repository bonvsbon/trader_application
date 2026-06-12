<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import IntervalCountdown from "./components/IntervalCountdown.vue";
import { useTheme } from "./composables/useTheme";
import { api } from "./api/client";
import { useAuthStore } from "./stores/auth";

const { theme, toggle } = useTheme();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const publicPage = computed(() => Boolean(route.meta.public));

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
  timer = window.setInterval(loadStatus, 8000);
});
onUnmounted(() => timer && clearInterval(timer));
</script>

<template>
  <router-view v-if="publicPage" />
  <div v-else class="app">
    <aside class="sidebar">
      <div class="brand">
        <span class="mark" aria-hidden="true">◇</span>
        <span>ทางรอด</span>
      </div>

      <div class="nav-scroll">
        <div class="nav-group">
          <span class="nav-label">Trading</span>
          <nav class="nav" aria-label="Trading">
            <router-link to="/dashboard">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" />
              </svg>
              <span>Dashboard</span>
            </router-link>
            <router-link to="/order">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M12 8v8M8 12h8" />
              </svg>
              <span>Manual Order</span>
            </router-link>
            <router-link to="/strategy">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 18l5-6 4 3 7-9" /><path d="M17 6h3v3" />
              </svg>
              <span>Strategy</span>
            </router-link>
            <router-link to="/approvals">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 11l2 2 4-4" /><path d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
              </svg>
              <span>Approvals</span>
            </router-link>
          </nav>
        </div>

        <div class="nav-group">
          <span class="nav-label">Monitoring</span>
          <nav class="nav" aria-label="Monitoring">
            <router-link to="/risk">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z" /><path d="M9.5 12l1.8 1.8 3.4-3.6" />
              </svg>
              <span>Risk Monitor</span>
            </router-link>
            <router-link to="/history">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 4v4h4" /><path d="M12 8v4l3 2" />
              </svg>
              <span>History</span>
            </router-link>
            <router-link to="/analysis">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 3v3M12 18v3M4.2 7.5l2.6 1.5M17.2 15l2.6 1.5M4.2 16.5l2.6-1.5M17.2 9l2.6-1.5" /><circle cx="12" cy="12" r="4" />
              </svg>
              <span>AI Analysis</span>
            </router-link>
            <router-link to="/logs">
              <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
              </svg>
              <span>Logs</span>
            </router-link>
          </nav>
        </div>
      </div>

      <div class="spacer"></div>
      <div class="nav-group utility-nav">
        <span class="nav-label">Settings</span>
        <nav class="nav" aria-label="Settings">
          <router-link to="/account">
            <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.5h.01M7 16.5h.01" />
            </svg>
            <span>MT5 Account</span>
          </router-link>
          <router-link to="/settings/providers">
            <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z" />
            </svg>
            <span>Providers</span>
          </router-link>
          <router-link to="/settings/market-data">
            <svg class="ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M3 17l5-5 4 3 6-8" /><path d="M15 7h3v3" />
            </svg>
            <span>Market Data</span>
          </router-link>
        </nav>
      </div>
      <div class="countdown-slot"><IntervalCountdown /></div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="safety-strip grow" v-if="online && status">
          <div class="safety-item">
            <span class="lbl">Account</span>
            <span class="badge" :class="status.account.account_type">{{ status.account.account_type }}</span>
          </div>
          <div class="safety-item">
            <span class="lbl">Mode</span>
            <span class="badge no-dot mono">{{ status.trading_mode }}</span>
          </div>
          <div class="safety-item">
            <span class="lbl">Bridge</span>
            <span class="badge" :class="status.bridge_health">{{ status.bridge_health }}</span>
          </div>
          <div class="safety-item" v-if="status.safety_flags.emergency_stop">
            <span class="badge BLOCK">Emergency stop</span>
          </div>
          <div class="safety-item" v-if="status.safety_flags.auto_real_full_enabled">
            <span class="badge BLOCK">Auto-real live</span>
          </div>
        </div>
        <div class="safety-strip grow" v-else>
          <span class="badge UNKNOWN">Backend offline</span>
        </div>

        <div v-if="auth.user" class="user-chip">
          <span class="mono">{{ auth.user.mt5_login }}</span>
          <span class="muted">{{ auth.user.mt5_account.server }}</span>
          <button class="btn ghost sm" @click="logout">Sign out</button>
        </div>

        <button class="theme-toggle" @click="toggle" :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'" :title="theme === 'dark' ? 'Light theme' : 'Dark theme'">
          <svg v-if="theme === 'light'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
          <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
        </button>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>
