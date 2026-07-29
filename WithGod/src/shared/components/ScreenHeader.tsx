import { useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

const BACK_ICON = require("../assets/images/chevron-right.png");

interface ScreenHeaderProps {
  title: string;
  /** 우측 슬롯. 없으면 타이틀 정렬 유지를 위해 백 버튼과 같은 폭의 스페이서를 렌더링한다. */
  right?: ReactNode;
}

/** 뒤로가기 + 타이틀 + 우측 슬롯으로 구성된 공용 화면 헤더 */
export function ScreenHeader({ title, right }: ScreenHeaderProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const { headerPaddingTop } = useSafeAreaPadding();

  return (
    <View style={[styles.header, { paddingTop: headerPaddingTop }]}>
      <TouchableOpacity
        style={styles.backButton}
        onPress={() => router.back()}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={t("nav.backA11y")}
      >
        <Image
          source={BACK_ICON}
          style={styles.backIcon}
          contentFit="contain"
        />
      </TouchableOpacity>
      <Text style={styles.headerTitle}>{title}</Text>
      {right ?? <View style={styles.headerSpacer} />}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  backButton: {
    width: 32,
    height: 32,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  backIcon: {
    width: 8,
    height: 14,
    transform: [{ rotate: "180deg" }],
    tintColor: colors.textPrimary,
  },
  headerTitle: {
    flex: 1,
    fontSize: scaleFont(18),
    lineHeight: scaleFont(24),
    fontWeight: "600",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  headerSpacer: {
    width: 32,
  },
});
