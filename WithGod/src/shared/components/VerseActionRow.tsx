import { logAnalyticsEvent } from "@/shared/lib/analytics";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import * as Sharing from "expo-sharing";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { captureRef } from "react-native-view-shot";

/** 공유 이미지 카드의 고정 폭(pt). 캡처 해상도는 기기 스케일을 따른다 */
const SHARE_CARD_WIDTH = 340;
const COPY_FEEDBACK_MS = 1500;

type VerseActionRowProps = {
  /** "잠언 17:17" 형태 출처 */
  reference: string;
  /** 말씀 본문 */
  text: string;
  isSaved: boolean;
  onToggleSave: () => void;
  /** analytics 이벤트의 source 파라미터 (daily | recommend | bookmarks_screen 등) */
  analyticsSource: string;
  /**
   * 복사·공유에 함께 담을 풀이.
   *
   * 오늘의 말씀 풀이는 구절마다 한 번 생성해 전 사용자가 공유하는 전역
   * 콘텐츠라 넘겨도 안전하다. 반면 위로의 말씀 코멘트는 사용자가 입력한
   * 마음을 인용하므로 절대 넘기지 않는다.
   */
  note?: string;
  /** 하트 접근성 라벨. 없으면 reference 기반 기본 문구 */
  saveLabel?: string;
  style?: StyleProp<ViewStyle>;
};

/**
 * 말씀 카드 하단의 공용 액션 줄: 복사 · 공유 · 하트(저장).
 *
 * - 복사: 구절(+풀이) 텍스트를 클립보드에 넣고 아이콘을 잠깐 체크로 바꾼다.
 * - 공유: 같은 내용을 담은 카드를 오프스크린에 렌더해 PNG로 캡처, OS 공유
 *   시트로 넘긴다. 공유 시트가 없는 환경(웹 등)은 텍스트 복사로 폴백.
 */
export function VerseActionRow({
  reference,
  text,
  isSaved,
  onToggleSave,
  analyticsSource,
  note,
  saveLabel,
  style,
}: VerseActionRowProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [isSharing, setIsSharing] = useState(false);
  const shareViewRef = useRef<View>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const trimmedNote = note?.trim();
  const shareText = trimmedNote
    ? `"${text}"\n- ${reference}\n\n${trimmedNote}`
    : `"${text}"\n- ${reference}`;

  const handleCopy = async () => {
    try {
      await Clipboard.setStringAsync(shareText);
      setCopied(true);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), COPY_FEEDBACK_MS);
      void logAnalyticsEvent("verse_copy", {
        source: analyticsSource,
        reference,
      });
    } catch (error) {
      if (__DEV__) console.warn("[VerseActionRow] copy failed", error);
    }
  };

  // 오프스크린 카드가 마운트·렌더된 다음 프레임에 캡처해야 하므로
  // 상태 전환 후 effect 에서 진행한다 (기존 result.tsx 캡처 패턴과 동일)
  useEffect(() => {
    if (!isSharing) return;
    const timer = setTimeout(async () => {
      try {
        if (!(await Sharing.isAvailableAsync())) {
          // 공유 시트가 없는 환경(웹 등)은 텍스트 복사로 폴백
          await handleCopy();
          return;
        }
        const uri = await captureRef(shareViewRef, {
          format: "png",
          quality: 1,
          result: "tmpfile",
        });
        await Sharing.shareAsync(uri, {
          mimeType: "image/png",
          dialogTitle: t("verseActions.shareDialogTitle"),
        });
        void logAnalyticsEvent("verse_share", {
          source: analyticsSource,
          reference,
        });
      } catch (error) {
        if (__DEV__) console.warn("[VerseActionRow] share failed", error);
      } finally {
        setIsSharing(false);
      }
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSharing]);

  return (
    <>
      {/* 복사 · 공유 · 하트 순 — 가장 자주 쓰는 하트를 엄지가 닿기 쉬운 우측 끝에 */}
      <View style={[styles.row, style]}>
        <TouchableOpacity
          onPress={handleCopy}
          hitSlop={{ top: 10, bottom: 10, left: 8, right: 8 }}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={t("verseActions.copyA11y", { reference })}
        >
          <Ionicons
            name={copied ? "checkmark" : "copy-outline"}
            size={20}
            color={copied ? colors.primary : colors.iconMuted}
          />
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => setIsSharing(true)}
          disabled={isSharing}
          hitSlop={{ top: 10, bottom: 10, left: 8, right: 8 }}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={t("verseActions.shareA11y", { reference })}
        >
          <Ionicons
            name={isSharing ? "hourglass-outline" : "share-outline"}
            size={20}
            color={colors.iconMuted}
          />
        </TouchableOpacity>
        <TouchableOpacity
          onPress={onToggleSave}
          hitSlop={{ top: 10, bottom: 10, left: 8, right: 8 }}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={
            saveLabel ??
            (isSaved
              ? t("verseActions.unsaveA11y", { reference })
              : t("verseActions.saveA11y", { reference }))
          }
        >
          <Ionicons
            name={isSaved ? "heart" : "heart-outline"}
            size={21}
            color={isSaved ? colors.heartActive : colors.iconMuted}
          />
        </TouchableOpacity>
      </View>

      {/* 공유용 오프스크린 카드 — 공유 진행 중에만 렌더 */}
      {isSharing && (
        <View style={styles.shareOffscreen} pointerEvents="none">
          <View
            ref={shareViewRef}
            collapsable={false}
            style={styles.shareCanvas}
          >
            <View style={styles.shareCard}>
              <Text style={styles.shareVerseText}>
                {'"'}
                {text}
                {'"'}
              </Text>
              <Text style={styles.shareReference}>{reference}</Text>
              {!!trimmedNote && (
                <>
                  <View style={styles.shareDivider} />
                  <Text style={styles.shareNoteText}>{trimmedNote}</Text>
                </>
              )}
            </View>
          </View>
        </View>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 20,
  },
  shareOffscreen: {
    position: "absolute",
    top: 0,
    left: -SHARE_CARD_WIDTH - 100,
    width: SHARE_CARD_WIDTH,
    overflow: "hidden",
  },
  shareCanvas: {
    width: SHARE_CARD_WIDTH,
    backgroundColor: colors.background,
    padding: 24,
  },
  shareCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    paddingHorizontal: 24,
    paddingVertical: 28,
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  shareVerseText: {
    fontSize: scaleFont(17),
    lineHeight: scaleFont(28),
    color: "#1E2939",
    fontFamily: baseFontFamily,
    marginBottom: 14,
  },
  shareReference: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: colors.primary,
    fontFamily: baseFontFamily,
    alignSelf: "flex-end",
  },
  shareDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginTop: 18,
    marginBottom: 16,
  },
  shareNoteText: {
    fontSize: scaleFont(13),
    lineHeight: scaleFont(22),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
});
