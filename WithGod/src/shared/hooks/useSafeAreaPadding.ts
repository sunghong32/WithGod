import { useMemo } from "react";
import { Platform, StatusBar } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

export function useSafeAreaPadding() {
  const insets = useSafeAreaInsets();

  const headerPaddingTop = useMemo(() => {
    return Platform.OS === "android"
      ? (StatusBar.currentHeight ?? 0) + 12
      : insets.top + 12;
  }, [insets.top]);

  const getInputBarPaddingBottom = useMemo(() => {
    return (isKeyboardVisible: boolean) => {
      // 키보드 올라오면 16, 내려가면 SafeArea 하단 + 16
      if (isKeyboardVisible) {
        return 16;
      }
      return insets.bottom + 16;
    };
  }, [insets.bottom]);

  return {
    insets,
    headerPaddingTop,
    getInputBarPaddingBottom,
  };
}
