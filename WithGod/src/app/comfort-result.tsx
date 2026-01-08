import { useRecommend, type RecommendItem } from "@/features/verse";
import { useSafeAreaPadding } from "@/shared/hooks";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

type SearchParams = {
  message?: string | string[];
};

const MOCK_RECOMMEND_RESULTS: RecommendItem[] = [
  {
    ref: "시편 23:1",
    text: "여호와는 나의 목자시니 내게 부족함이 없으리로다.",
    comment:
      "지금은 불안을 혼자 견디지 말고, 하루를 맡기며 한 걸음씩 가도 괜찮습니다.",
    tag: "두려움",
  },
  {
    ref: "빌립보서 4:6",
    text: "아무것도 염려하지 말고 다만 모든 일에 기도와 간구로 너희 구할 것을 감사함으로 하나님께 아뢰라.",
    comment:
      "걱정이 올라올 때마다 한 문장 기도로 바꿔보면 마음의 소음이 조금씩 잦아듭니다.",
    tag: "걱정",
  },
];

export default function ComfortResultScreen() {
  const params = useLocalSearchParams<SearchParams>();
  const router = useRouter();
  const { insets } = useSafeAreaPadding();
  const [hasRequested, setHasRequested] = useState(false);
  const { mutate, data, isPending, isError, reset } = useRecommend();

  const userMessage = useMemo(() => {
    const raw = params.message;
    if (!raw) return "";
    if (Array.isArray(raw)) return raw[0] ?? "";
    return raw;
  }, [params.message]);

  useEffect(() => {
    if (!userMessage.trim() || hasRequested) {
      return;
    }

    setHasRequested(true);
    mutate({ mood: userMessage.trim() });
  }, [mutate, userMessage, hasRequested]);

  const handleRetry = () => {
    reset();
    setHasRequested(false);
  };

  const handleBack = () => {
    router.back();
  };

  const handleSearchAgain = () => {
    const mood = userMessage.trim();
    if (!mood) {
      return;
    }

    setHasRequested(true);
    reset();
    mutate({ mood });
  };

  const resultItems = data?.results ?? [];
  const shouldUseMockResults = !isPending && (isError || resultItems.length === 0);
  const displayedItems = shouldUseMockResults ? MOCK_RECOMMEND_RESULTS : resultItems;

  return (
    <View style={styles.root}>
      <SafeAreaView
        style={[
          styles.safeArea,
          {
            paddingTop: insets.top,
            paddingBottom: Platform.OS === "ios" ? 0 : insets.bottom,
          },
        ]}
        edges={["left", "right"]}
      >
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={handleBack}
            accessibilityRole="button"
            accessibilityLabel="이전 화면으로 돌아가기"
          >
            <Ionicons name="chevron-back" size={22} color="#1E2939" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>위로의 말씀</Text>
          <View style={styles.headerSpacer} />
        </View>

        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {!!userMessage && (
            <View style={styles.messageBubble}>
              <Text style={styles.messageText}>{userMessage}</Text>
            </View>
          )}

          <Text style={styles.sectionTitle}>당신을 위한 말씀</Text>

          <View style={styles.resultsContainer}>
            {isPending ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#4A90E2" />
                <Text style={styles.loadingText}>말씀을 준비하고 있어요...</Text>
              </View>
            ) : (
              <>
                {shouldUseMockResults && (
                  <View style={styles.errorContainer}>
                    <Text style={styles.errorTitle}>말씀을 불러오지 못했어요</Text>
                    <Text style={styles.errorDescription}>다시 시도해주세요.</Text>
                    <Text style={styles.mockNoticeText}>예시 데이터를 대신 보여드리고 있어요.</Text>
                    <TouchableOpacity
                      style={styles.retryButton}
                      onPress={handleRetry}
                      accessibilityRole="button"
                    >
                      <Text style={styles.retryButtonText}>다시 시도하기</Text>
                    </TouchableOpacity>
                  </View>
                )}
                {displayedItems.map((item) => (
                  <ResultCard key={item.ref} item={item} />
                ))}
              </>
            )}
          </View>
        </ScrollView>

        <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={handleSearchAgain}
            accessibilityRole="button"
          >
            <Text style={styles.secondaryButtonText}>다시 검색하기</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </View>
  );
}

function ResultCard({ item }: { item: RecommendItem }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardVerseText}>“{item.text}”</Text>
      <View style={styles.cardMeta}>
        <Text style={styles.cardReference}>{item.ref}</Text>
        {item.tag ? (
          <View style={styles.tag}>
            <Text style={styles.tagText}>{item.tag}</Text>
          </View>
        ) : null}
      </View>
      {item.comment ? (
        <View style={styles.commentBox}>
          <Text style={styles.commentText}>{item.comment}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  safeArea: {
    flex: 1,
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#E5E7EB",
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  backButton: {
    height: 32,
    width: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "600",
    color: "#101828",
  },
  headerSpacer: {
    width: 32,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 120,
    gap: 24,
  },
  messageBubble: {
    alignSelf: "flex-end",
    backgroundColor: "#4A90E2",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 8,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 16,
    maxWidth: "85%",
  },
  messageText: {
    fontSize: 16,
    lineHeight: 26,
    color: "#FFFFFF",
  },
  sectionTitle: {
    fontSize: 18,
    lineHeight: 28,
    color: "#101828",
    fontWeight: "500",
  },
  resultsContainer: {
    gap: 16,
  },
  loadingContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    paddingVertical: 48,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  loadingText: {
    fontSize: 16,
    color: "#4A5565",
  },
  errorContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    paddingHorizontal: 24,
    paddingVertical: 32,
    alignItems: "center",
    gap: 12,
  },
  errorTitle: {
    fontSize: 18,
    color: "#101828",
    fontWeight: "600",
  },
  errorDescription: {
    fontSize: 15,
    color: "#4A5565",
    textAlign: "center",
    lineHeight: 22,
  },
  mockNoticeText: {
    fontSize: 14,
    color: "#4A5565",
    textAlign: "center",
    lineHeight: 21,
  },
  retryButton: {
    marginTop: 8,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#4A90E2",
  },
  retryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "600",
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    paddingHorizontal: 24,
    paddingVertical: 24,
    gap: 20,
  },
  cardVerseText: {
    fontSize: 20,
    lineHeight: 32,
    color: "#1E2939",
    fontWeight: "500",
  },
  cardMeta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardReference: {
    fontSize: 16,
    lineHeight: 24,
    color: "#4A90E2",
    fontWeight: "600",
  },
  tag: {
    backgroundColor: "#F3F4F6",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  tagText: {
    fontSize: 12,
    color: "#6A7282",
  },
  commentBox: {
    backgroundColor: "#F5F3F0",
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  commentText: {
    fontSize: 16,
    lineHeight: 27,
    color: "#8B7355",
  },
  footer: {
    backgroundColor: "#F9FAFB",
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopColor: "rgba(229, 231, 235, 0.8)",
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  secondaryButton: {
    height: 44,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#4A90E2",
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButtonText: {
    fontSize: 18,
    color: "#4A90E2",
    fontWeight: "600",
  },
});

