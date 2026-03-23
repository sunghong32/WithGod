import { Platform } from "react-native";

export const baseFontFamily = Platform.select({
  ios: "System",
  android: "Roboto",
  web: "sans-serif",
  default: "sans-serif",
});

export const fontScale = Platform.select({
  ios: 1.0,
  android: 1.0,
  web: 1.0,
  default: 1.0,
});

export const scaleFont = (size: number) =>
  Math.round(size * (fontScale ?? 1));
