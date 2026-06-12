import { ref } from "vue";

export type Theme = "light" | "dark";

function initial(): Theme {
  try {
    const stored = localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") return stored;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

// Shared singleton so every component reflects the same theme.
const theme = ref<Theme>(initial());

function apply(value: Theme) {
  document.documentElement.dataset.theme = value;
}
apply(theme.value);

export function useTheme() {
  function toggle() {
    theme.value = theme.value === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("theme", theme.value);
    } catch {
      /* ignore storage errors */
    }
    apply(theme.value);
  }
  return { theme, toggle };
}
