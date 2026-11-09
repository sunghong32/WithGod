import { useMemo } from "react";
import { useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

/**
 * 본문 단의 최대 폭(dp, 좌우 기본 여백 포함).
 *
 * 태블릿·폴더블은 화면이 1,000dp 를 넘어 본문을 그대로 늘리면 한 줄이 150자까지
 * 길어진다(이슈 #26). 가독 폭(한 줄 45~75자)에 맞춰 이 폭을 넘는 화면에서는 양옆 여백을
 * 늘려 본문을 가운데로 모은다. 폰(440dp 안팎까지)은 이보다 좁아 아무것도 달라지지 않는다.
 */
export const CONTENT_MAX_WIDTH = 640;

export function useSafeAreaPadding() {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();

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

  // 화면 끝까지 닿는 바(헤더)의 좌우 여백. 가로 화면의 노치·카메라 컷아웃을 피한다.
  // 세로에서는 좌우 안전영역이 0 이라 기본 여백 그대로다.
  const getSidePadding = useMemo(() => {
    return (base: number) => ({
      paddingLeft: base + insets.left,
      paddingRight: base + insets.right,
    });
  }, [insets.left, insets.right]);

  // 본문(스크롤 내용·입력창)의 좌우 여백. 안전영역을 피하고, 화면이 넓으면
  // CONTENT_MAX_WIDTH 폭의 단으로 가운데에 모은다.
  const getContentPadding = useMemo(() => {
    const centering = Math.max(0, (width - CONTENT_MAX_WIDTH) / 2);
    return (base: number) => ({
      paddingLeft: base + Math.max(insets.left, centering),
      paddingRight: base + Math.max(insets.right, centering),
    });
  }, [width, insets.left, insets.right]);

  return {
    insets,
    headerPaddingTop,
    getInputBarPaddingBottom,
    getSidePadding,
    getContentPadding,
  };
}
