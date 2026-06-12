<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const loading = ref(false);
const error = ref<string | null>(null);
const loginForm = reactive({ mt5Login: null as number | null, appPassword: "" });
const setupForm = reactive({
  displayName: "",
  mt5Login: null as number | null,
  mt5Server: "",
  accountType: "DEMO" as "DEMO" | "REAL",
  appPassword: "",
  confirmPassword: "",
});
const setupMode = computed(() => auth.bootstrapRequired);

function errorText(value: any) {
  return value?.response?.data?.detail ?? value?.message ?? "Authentication failed";
}

async function submitLogin() {
  if (!loginForm.mt5Login) return;
  loading.value = true;
  error.value = null;
  try {
    await auth.login(loginForm.mt5Login, loginForm.appPassword);
    await router.replace(String(route.query.redirect || "/dashboard"));
  } catch (value: any) {
    error.value = errorText(value);
  } finally {
    loading.value = false;
  }
}

async function submitSetup() {
  if (!setupForm.mt5Login) return;
  if (setupForm.appPassword !== setupForm.confirmPassword) {
    error.value = "App passwords do not match.";
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    await auth.bootstrap({
      mt5_login: setupForm.mt5Login,
      app_password: setupForm.appPassword,
      display_name: setupForm.displayName,
      mt5_server: setupForm.mt5Server,
      account_type: setupForm.accountType,
    });
    await router.replace("/dashboard");
  } catch (value: any) {
    error.value = errorText(value);
  } finally {
    loading.value = false;
  }
}

onMounted(() => auth.initialize(true).catch(() => undefined));
</script>

<template>
  <main class="login-shell">
    <section class="login-card">
      <div class="login-brand">
        <span class="login-mark">◇</span>
        <div>
          <h1>ทางรอด</h1>
          <p>{{ setupMode ? "Create the first account owner" : "Sign in to your trading cockpit" }}</p>
        </div>
      </div>

      <div class="notice neutral">
        Your username is your MT5 login number. Use a separate app password here.
        Never enter your broker or MT5 master password into this application.
      </div>
      <div v-if="error" class="notice">{{ error }}</div>

      <form v-if="setupMode" @submit.prevent="submitSetup">
        <div class="field">
          <label>Display name</label>
          <input v-model.trim="setupForm.displayName" required minlength="2" autocomplete="name" />
        </div>
        <div class="field">
          <label>MT5 login</label>
          <input v-model.number="setupForm.mt5Login" type="number" min="1" required autocomplete="username" />
        </div>
        <div class="field">
          <label>MT5 server</label>
          <input v-model.trim="setupForm.mt5Server" required placeholder="Broker-Demo" />
        </div>
        <div class="field">
          <label>Account type</label>
          <select v-model="setupForm.accountType">
            <option value="DEMO">DEMO</option>
            <option value="REAL">REAL</option>
          </select>
        </div>
        <div class="field">
          <label>New app password</label>
          <input v-model="setupForm.appPassword" type="password" minlength="10" maxlength="128" required autocomplete="new-password" />
        </div>
        <div class="field">
          <label>Confirm app password</label>
          <input v-model="setupForm.confirmPassword" type="password" minlength="10" maxlength="128" required autocomplete="new-password" />
        </div>
        <button class="btn full" type="submit" :disabled="loading">
          <span v-if="loading" class="spin"></span>
          Create owner account
        </button>
      </form>

      <form v-else @submit.prevent="submitLogin">
        <div class="field">
          <label>MT5 login</label>
          <input v-model.number="loginForm.mt5Login" type="number" min="1" required autocomplete="username" autofocus />
        </div>
        <div class="field">
          <label>App password</label>
          <input v-model="loginForm.appPassword" type="password" minlength="10" maxlength="128" required autocomplete="current-password" />
        </div>
        <button class="btn full" type="submit" :disabled="loading">
          <span v-if="loading" class="spin"></span>
          Sign in
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--sp-7);
  background: var(--bg);
}
.login-card {
  width: min(100%, 460px);
  padding: var(--sp-8);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
}
.login-brand {
  display: flex;
  align-items: center;
  gap: var(--sp-5);
  margin-bottom: var(--sp-7);
}
.login-brand h1 { margin: 0; }
.login-brand p { margin-top: var(--sp-2); color: var(--ink-muted); }
.login-mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: var(--r-md);
  background: var(--accent);
  color: var(--on-accent);
  font-size: 1.4rem;
}
.notice { margin-bottom: var(--sp-6); }
.notice.neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
.full { width: 100%; }
</style>
