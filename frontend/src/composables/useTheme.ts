import { ref, watch } from "vue";

export type Theme = "light" | "dark";
export type Density = "compact" | "cozy";

export interface Accent {
  name: string;
  h: number;
}

export const ACCENTS: Accent[] = [
  { name: "Blue", h: 255 },
  { name: "Teal", h: 195 },
  { name: "Violet", h: 295 },
  { name: "Amber", h: 75 },
];

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore storage errors */
  }
}

function initialTheme(): Theme {
  const stored = read("theme");
  if (stored === "light" || stored === "dark") return stored;
  try {
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

// Shared singletons so every component reflects the same preferences.
const theme = ref<Theme>(initialTheme());
const accent = ref<number>(Number(read("tr-accent")) || 255);
const density = ref<Density>((read("tr-dense") as Density) || "cozy");
const mono = ref<boolean>(read("tr-mono") !== "0");

function applyTheme(value: Theme) {
  document.documentElement.dataset.theme = value;
}

function applyAccent(h: number, t: Theme) {
  const r = document.documentElement.style;
  const dark = t === "dark";
  r.setProperty("--accent", `oklch(${dark ? 0.7 : 0.55} 0.15 ${h})`);
  r.setProperty("--accent-hover", `oklch(${dark ? 0.75 : 0.5} 0.16 ${h})`);
  r.setProperty("--accent-ink", `oklch(${dark ? 0.74 : 0.46} 0.16 ${h})`);
  r.setProperty(
    "--accent-soft",
    `oklch(${dark ? 0.7 : 0.55} 0.15 ${h} / ${dark ? 0.16 : 0.1})`,
  );
}

function applyDensity(value: Density) {
  document.documentElement.style.setProperty("--density", value === "compact" ? "0.82" : "1");
}

function applyMono(value: boolean) {
  document.documentElement.style.setProperty("--mono-num", value ? "var(--font-mono)" : "var(--font-sans)");
}

// Apply current state once on module load.
applyTheme(theme.value);
applyAccent(accent.value, theme.value);
applyDensity(density.value);
applyMono(mono.value);

watch(theme, (v) => {
  applyTheme(v);
  applyAccent(accent.value, v);
  write("theme", v);
});
watch(accent, (v) => {
  applyAccent(v, theme.value);
  write("tr-accent", String(v));
});
watch(density, (v) => {
  applyDensity(v);
  write("tr-dense", v);
});
watch(mono, (v) => {
  applyMono(v);
  write("tr-mono", v ? "1" : "0");
});

export function useTheme() {
  function toggle() {
    theme.value = theme.value === "dark" ? "light" : "dark";
  }
  return { theme, toggle, accent, density, mono };
}
