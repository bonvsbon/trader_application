import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    {
      path: "/login",
      name: "login",
      component: () => import("../pages/LoginPage.vue"),
      meta: { public: true },
    },
    { path: "/dashboard", name: "dashboard", component: () => import("../pages/DashboardPage.vue") },
    { path: "/order", name: "order", component: () => import("../pages/ManualOrderPage.vue") },
    { path: "/chart", name: "chart", component: () => import("../pages/ChartPage.vue") },
    { path: "/approvals", name: "approvals", component: () => import("../pages/ApprovalsPage.vue") },
    { path: "/strategy", name: "strategy", component: () => import("../pages/StrategyPage.vue") },
    { path: "/account", name: "account", component: () => import("../pages/Mt5AccountPage.vue") },
    { path: "/risk", name: "risk", component: () => import("../pages/RiskMonitorPage.vue") },
    { path: "/history", name: "history", component: () => import("../pages/HistoryPage.vue") },
    { path: "/logs", name: "logs", component: () => import("../pages/LogsPage.vue") },
    { path: "/analysis", name: "analysis", component: () => import("../pages/AIAnalysisPage.vue") },
    {
      path: "/settings/providers",
      name: "analysis-providers",
      component: () => import("../pages/AnalysisProvidersPage.vue"),
    },
    {
      path: "/settings/market-data",
      name: "market-data-settings",
      component: () => import("../pages/MarketDataSettingsPage.vue"),
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  try {
    await auth.initialize();
  } catch {
    if (to.meta.public) return true;
    return { name: "login" };
  }
  if (to.meta.public) {
    if (to.name === "login" && auth.enabled && auth.authenticated) {
      return { name: "dashboard" };
    }
    return true;
  }
  if (auth.enabled && !auth.authenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  return true;
});
