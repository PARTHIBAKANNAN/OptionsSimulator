/**
 * Chart Palette Presets & Custom Layer Color Studio Utilities
 */

export const PALETTE_PRESETS = {
  pro_dark: {
    id: "pro_dark",
    name: "Pro Dark (Neon Emerald)",
    upColor: "#10b981",
    downColor: "#f43f5e",
    vwapColor: "#eab308",
    ema20Color: "#06b6d4",
    ema50Color: "#f97316",
    volumeUp: "#10b981",
    volumeDown: "#f43f5e",
  },
  classic_tv: {
    id: "classic_tv",
    name: "Classic TradingView",
    upColor: "#26a69a",
    downColor: "#ef5350",
    vwapColor: "#ff9800",
    ema20Color: "#2962ff",
    ema50Color: "#e91e63",
    volumeUp: "#26a69a",
    volumeDown: "#ef5350",
  },
  cyberpunk: {
    id: "cyberpunk",
    name: "Midnight Cyberpunk",
    upColor: "#00f0ff",
    downColor: "#ff007f",
    vwapColor: "#ffff00",
    ema20Color: "#a855f7",
    ema50Color: "#ff8000",
    volumeUp: "#00f0ff",
    volumeDown: "#ff007f",
  },
  colorblind: {
    id: "colorblind",
    name: "High-Contrast (Blue/Orange)",
    upColor: "#3b82f6",
    downColor: "#f97316",
    vwapColor: "#a855f7",
    ema20Color: "#14b8a6",
    ema50Color: "#ec4899",
    volumeUp: "#3b82f6",
    volumeDown: "#f97316",
  },
};

export const DEFAULT_PALETTE_ID = "pro_dark";

export function getActivePalette() {
  if (typeof localStorage === "undefined") {
    return { ...PALETTE_PRESETS[DEFAULT_PALETTE_ID], isCustom: false };
  }
  try {
    const raw = localStorage.getItem("nukebox_chart_palette");
    if (!raw) return { ...PALETTE_PRESETS[DEFAULT_PALETTE_ID], isCustom: false };
    const parsed = JSON.parse(raw);
    if (parsed.isCustom) {
      return parsed;
    }
    const preset = PALETTE_PRESETS[parsed.presetId || parsed.id];
    return preset ? { ...preset, isCustom: false } : { ...PALETTE_PRESETS[DEFAULT_PALETTE_ID], isCustom: false };
  } catch {
    return { ...PALETTE_PRESETS[DEFAULT_PALETTE_ID], isCustom: false };
  }
}

export function savePresetPalette(presetId) {
  if (typeof localStorage === "undefined") return;
  const preset = PALETTE_PRESETS[presetId] || PALETTE_PRESETS[DEFAULT_PALETTE_ID];
  localStorage.setItem(
    "nukebox_chart_palette",
    JSON.stringify({ ...preset, isCustom: false, presetId })
  );
  window.dispatchEvent(new Event("nukebox_palette_changed"));
}

export function saveCustomPalette(customColors) {
  if (typeof localStorage === "undefined") return;
  const merged = {
    ...PALETTE_PRESETS[DEFAULT_PALETTE_ID],
    ...customColors,
    isCustom: true,
    id: "custom",
    name: "Custom Palette",
  };
  localStorage.setItem("nukebox_chart_palette", JSON.stringify(merged));
  window.dispatchEvent(new Event("nukebox_palette_changed"));
}

