import { defineStore } from "pinia";
import { api, setCsrfToken, type AuthStatus, type AuthUser } from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    initialized: false,
    enabled: false,
    bootstrapRequired: false,
    authenticated: false,
    user: null as AuthUser | null,
  }),
  actions: {
    apply(status: AuthStatus) {
      this.enabled = status.enabled;
      this.bootstrapRequired = status.bootstrap_required;
      this.authenticated = status.authenticated;
      this.user = status.user;
      setCsrfToken(status.csrf_token ?? null);
      this.initialized = true;
    },
    async initialize(force = false) {
      if (this.initialized && !force) return;
      this.apply(await api.authStatus());
    },
    async login(mt5Login: number, appPassword: string) {
      const result = await api.login(mt5Login, appPassword);
      setCsrfToken(result.csrf_token);
      await this.initialize(true);
    },
    async bootstrap(payload: {
      mt5_login: number;
      app_password: string;
      display_name: string;
      mt5_server: string;
      account_type: "DEMO" | "REAL";
    }) {
      const result = await api.bootstrapUser(payload);
      setCsrfToken(result.csrf_token);
      await this.initialize(true);
    },
    async logout() {
      await api.logout();
      setCsrfToken(null);
      this.authenticated = false;
      this.user = null;
      await this.initialize(true);
    },
  },
});
