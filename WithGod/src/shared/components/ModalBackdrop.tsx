import type { ReactNode } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

/**
 * 가운데 카드형 모달의 어두운 배경. 카드를 children 으로 받는다.
 *
 * 배경 자체가 스크롤된다. 높이가 낮은 창(태블릿 가로·분할 화면, 큰 글씨)에서는 카드가
 * 화면보다 길어질 수 있는데, 그냥 가운데에 두면 아래 버튼이 화면 밖으로 밀려 **모달을
 * 닫을 방법이 없어진다**(이슈 #26 — 뒤로가기를 막아 둔 통계 동의창은 앱이 잠긴다).
 * 카드가 다 들어가면 스크롤 없이 지금처럼 가운데에 놓인다.
 */
export function ModalBackdrop({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  // 위아래를 같은 값으로 띄워야 카드가 들어갈 때 정확히 가운데에 놓인다
  const verticalPadding = Math.max(insets.top, insets.bottom) + 16;

  return (
    <View style={styles.backdrop}>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: verticalPadding,
            paddingBottom: verticalPadding,
            paddingLeft: 32 + insets.left,
            paddingRight: 32 + insets.right,
          },
        ]}
        bounces={false}
      >
        {children}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(16, 24, 40, 0.45)",
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
  },
});
