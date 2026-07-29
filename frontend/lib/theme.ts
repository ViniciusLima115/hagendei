import type { CSSProperties } from "react";

export const DEFAULT_ACCENT_COLOR = "#1e3a5f";
export const DEFAULT_BACKGROUND_COLOR = "#ffffff";

type Rgb = {
  r: number;
  g: number;
  b: number;
};

export type ResolvedThemeMode = "light" | "dark";

export type TenantThemeVariables = CSSProperties & Record<`--${string}`, string>;

function clampChannel(value: number) {
  return Math.max(0, Math.min(255, Math.round(value)));
}

function normalizeHex(value: string | null | undefined, fallback: string) {
  const normalized = value?.trim().toLowerCase();
  return normalized && /^#[0-9a-f]{6}$/.test(normalized) ? normalized : fallback;
}

function hexToRgb(hex: string): Rgb {
  return {
    r: Number.parseInt(hex.slice(1, 3), 16),
    g: Number.parseInt(hex.slice(3, 5), 16),
    b: Number.parseInt(hex.slice(5, 7), 16),
  };
}

function rgbToHex({ r, g, b }: Rgb) {
  return `#${[r, g, b]
    .map((channel) => clampChannel(channel).toString(16).padStart(2, "0"))
    .join("")}`;
}

function mix(first: string, second: string, secondWeight: number) {
  const a = hexToRgb(first);
  const b = hexToRgb(second);
  const weight = Math.max(0, Math.min(1, secondWeight));

  return rgbToHex({
    r: a.r * (1 - weight) + b.r * weight,
    g: a.g * (1 - weight) + b.g * weight,
    b: a.b * (1 - weight) + b.b * weight,
  });
}

function withAlpha(hex: string, alpha: number) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function relativeLuminance(hex: string) {
  const channels = Object.values(hexToRgb(hex)).map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first: string, second: string) {
  const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
  const darker = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

function readableForeground(background: string) {
  const light = "#ffffff";
  const dark = "#10213b";
  return contrastRatio(light, background) >= contrastRatio(dark, background) ? light : dark;
}

function ensureTextContrast(color: string, background: string, minimum = 4.5) {
  if (contrastRatio(color, background) >= minimum) return color;

  const target =
    contrastRatio("#10213b", background) >= contrastRatio("#ffffff", background)
      ? "#10213b"
      : "#ffffff";

  for (let amount = 0.08; amount <= 1; amount += 0.08) {
    const candidate = mix(color, target, amount);
    if (contrastRatio(candidate, background) >= minimum) return candidate;
  }

  return target;
}

export function createTenantThemeVariables(
  accentValue?: string | null,
  backgroundValue?: string | null,
  mode: ResolvedThemeMode = "light",
): TenantThemeVariables {
  const accent = normalizeHex(accentValue, DEFAULT_ACCENT_COLOR);
  const tenantBackground = normalizeHex(backgroundValue, DEFAULT_BACKGROUND_COLOR);
  const tenantBackgroundIsDark = relativeLuminance(tenantBackground) < 0.2;

  const canvas =
    mode === "dark" && !tenantBackgroundIsDark
      ? mix(tenantBackground, "#10141c", 0.9)
      : tenantBackground;
  const darkCanvas = relativeLuminance(canvas) < 0.24;
  const ink = darkCanvas ? "#f5f7fb" : "#152238";
  const inkMuted = mix(ink, canvas, darkCanvas ? 0.35 : 0.42);
  const inkSubtle = mix(ink, canvas, darkCanvas ? 0.55 : 0.58);
  const surface = darkCanvas ? mix(canvas, "#ffffff", 0.065) : mix(canvas, "#ffffff", 0.82);
  const surfaceAlt = darkCanvas ? mix(canvas, "#ffffff", 0.12) : mix(canvas, ink, 0.045);
  const line = darkCanvas ? mix(canvas, "#ffffff", 0.17) : mix(surface, ink, 0.11);

  const onAccent = readableForeground(accent);
  const accentPanel = mix(accent, "#10213b", relativeLuminance(accent) > 0.18 ? 0.3 : 0.14);
  const onAccentPanel = readableForeground(accentPanel);
  const accentStrong = ensureTextContrast(accent, surface);
  const accentSoft = mix(surface, accent, darkCanvas ? 0.24 : 0.12);
  const logoPrimary = ensureTextContrast(accent, "#ffffff", 3);
  const logoSecondary = ensureTextContrast(accentPanel, "#ffffff", 3);
  const logoRibbon = ensureTextContrast(accent, "#ffffff", 2);
  const accentHover = mix(
    accent,
    onAccent === "#ffffff" ? "#ffffff" : "#10213b",
    onAccent === "#ffffff" ? 0.1 : 0.12,
  );

  return {
    "--accent": accent,
    "--accent-tenant": accent,
    "--accent-dark": accentStrong,
    "--accent-strong": accentStrong,
    "--accent-hover": accentHover,
    "--accent-soft": accentSoft,
    "--accent-ring": withAlpha(accent, darkCanvas ? 0.34 : 0.22),
    "--accent-panel": accentPanel,
    "--on-accent": onAccent,
    "--on-accent-panel": onAccentPanel,
    "--logo-primary": logoPrimary,
    "--logo-secondary": logoSecondary,
    "--logo-ribbon": logoRibbon,
    "--bg-tenant": tenantBackground,
    "--tenant-color-scheme": darkCanvas ? "dark" : "light",
    "--canvas": canvas,
    "--surface": surface,
    "--surface-alt": surfaceAlt,
    "--line": line,
    "--ink": ink,
    "--ink-muted": inkMuted,
    "--ink-subtle": inkSubtle,
    "--warm": accent,
    "--warm-soft": accentSoft,
    "--tenant-shadow": darkCanvas
      ? "0 18px 44px rgba(0, 0, 0, 0.34)"
      : "0 18px 44px rgba(16, 33, 59, 0.10)",
  };
}

export function applyTenantTheme(
  element: HTMLElement,
  accent?: string | null,
  background?: string | null,
  mode?: ResolvedThemeMode,
) {
  const resolvedMode =
    mode ?? (element.dataset.theme === "dark" ? "dark" : "light");
  const variables = createTenantThemeVariables(accent, background, resolvedMode);

  Object.entries(variables).forEach(([property, value]) => {
    if (typeof value === "string") element.style.setProperty(property, value);
  });
  element.style.colorScheme =
    variables["--tenant-color-scheme"] === "dark" ? "dark" : "light";
}
