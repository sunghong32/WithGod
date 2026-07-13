import { useMemo } from "react";
import { useSafeAreaInsets } from "react-native-safe-area-context";

export function useSafeAreaPadding() {
  const insets = useSafeAreaInsets();

  // edge-to-edge 기준: 양 플랫폼 모두 창이 상태바 뒤까지 그려지므로 insets.top 만 쓴다.
  // (Android 에서 StatusBar.currentHeight 를 더하면 상태바 높이가 이중으로 들어간다)
  const headerPaddingTop = useMemo(() => insets.top + 12, [insets.top]);

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
