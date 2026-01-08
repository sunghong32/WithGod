import { Platform } from "react-native";

export const baseFontFamily = Platform.select({
  ios: "System",
  android: "Roboto",
  web: "sans-serif",
  default: "sans-serif",
});
