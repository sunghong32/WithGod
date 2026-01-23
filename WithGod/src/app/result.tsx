import { verseApi, ApiError } from "@/features/verse";
import { parseError } from "@/shared/api/errors";
import { useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily } from "@/shared/styles";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const BACK_ICON = require("../shared/assets/images/chevron-right.png");

export default function ResultScreen() {
  const router = useRouter();
  const { mood } = useLocalSearchParams<{ mood: string }>();
  const { insets, headerPaddingTop } = useSafeAreaPadding();

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["verse", "recommend", mood],
    queryFn: () => verseApi.getRecommendation({ mood: mood ?? "" }),
    enabled: !!mood,
    retry: (failureCount, err) => {
      const apiError = parseError(err);
      return apiError.isRetryable && failureCount < 2;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });

  const results = data?.results ?? [];
  const showLoading = isLoading || isFetching;
  const hasError = isError || (!showLoading && results.length === 0);

  // 에러 메시지 추출
  const errorMessage =
    error instanceof ApiError
      ? error.userMessage
      : hasError
        ? "말씀을 불러오지 못했어요"
        : null;

  return (
    <View style={styles.container}>
      {/* Header - 위로의 말씀 */}
      <View style={[styles.header, { paddingTop: headerPaddingTop }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <Image
            source={BACK_ICON}
            style={styles.backIcon}
            contentFit="contain"
          />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>위로의 말씀</Text>
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {/* 유저 입력 말풍선 - 오른쪽 정렬 */}
        <View style={styles.userMessageContainer}>
          <View style={styles.userMessageBubble}>
            <Text style={styles.userMessageText}>{mood}</Text>
          </View>
        </View>

        {/* 당신을 위한 말씀 섹션 */}
        <Text style={styles.sectionTitle}>당신을 위한 말씀</Text>

        {showLoading ? (
          // 로딩 중: 유저 메시지 아래에 로딩 표시
          <View style={styles.loadingCard}>
            <ActivityIndicator size="small" color="#4A90E2" style={styles.loadingIndicator} />
            <Text style={styles.loadingCardText}>말씀을 찾고 있어요...</Text>
          </View>
        ) : hasError ? (
          <TouchableOpacity
            style={styles.errorContainer}
            onPress={() => refetch()}
            activeOpacity={0.7}
          >
            <Text style={styles.errorTitle}>{errorMessage}</Text>
            <Text style={styles.errorDescription}>
              탭하여 다시 시도해주세요
            </Text>
          </TouchableOpacity>
        ) : (
          <>
            <View style={styles.resultsContainer}>
              {results.map((result, index) => (
                <View key={`${result.ref}-${index}`} style={styles.verseCard}>
                  {/* 성경 구절 */}
                  <Text style={styles.verseText}>"{result.text}"</Text>

                  {/* 레퍼런스와 태그 - 한 줄에 배치 */}
                  <View style={styles.referenceRow}>
                    <Text style={styles.verseReference}>{result.ref}</Text>
                    {result.tag && (
                      <View style={styles.tag}>
                        <Text style={styles.tagText}>{result.tag}</Text>
                      </View>
                    )}
                  </View>

                  {/* 코멘트 (말풍선 스타일) */}
                  {result.comment && (
                    <View style={styles.commentBubble}>
                      <Text style={styles.commentText}>{result.comment}</Text>
                    </View>
                  )}
                </View>
              ))}
            </View>

            {/* 다시 검색하기 버튼 */}
            <TouchableOpacity
              style={styles.searchAgainButton}
              onPress={() => refetch()}
              activeOpacity={0.7}
            >
              <Text style={styles.searchAgainButtonText}>다시 검색하기</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#E5E7EB",
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
    tintColor: "#101828",
  },
  headerTitle: {
    fontSize: 18,
    lineHeight: 24,
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
  },
  // 유저 메시지 - 오른쪽 정렬
  userMessageContainer: {
    alignItems: "flex-end",
    marginBottom: 24,
  },
  userMessageBubble: {
    backgroundColor: "#4A90E2",
    borderRadius: 16,
    borderBottomRightRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 12,
    maxWidth: "80%",
  },
  userMessageText: {
    fontSize: 16,
    lineHeight: 24,
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  // 섹션 타이틀
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#101828",
    marginBottom: 16,
    fontFamily: baseFontFamily,
  },
  // 로딩 카드
  loadingCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    padding: 20,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  loadingIndicator: {
    marginRight: 12,
  },
  loadingCardText: {
    fontSize: 16,
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
  // 에러
  errorContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(229, 231, 235, 0.9)",
    padding: 20,
    alignItems: "center",
  },
  errorTitle: {
    fontSize: 16,
    color: "#6A7282",
    marginBottom: 4,
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  errorDescription: {
    fontSize: 16,
    color: "#6A7282",
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  // 결과 컨테이너
  resultsContainer: {
    gap: 16,
  },
  // 말씀 카드
  verseCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    padding: 20,
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  verseText: {
    fontSize: 16,
    lineHeight: 26,
    color: "#1E2939",
    marginBottom: 8,
    fontFamily: baseFontFamily,
  },
  // 레퍼런스와 태그를 한 줄에 배치
  referenceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  verseReference: {
    fontSize: 14,
    fontWeight: "600",
    color: "#4A90E2",
    fontFamily: baseFontFamily,
  },
  // 태그
  tag: {
    backgroundColor: "rgba(106, 114, 130, 0.1)",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  tagText: {
    fontSize: 12,
    fontWeight: "500",
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
  // 코멘트 말풍선
  commentBubble: {
    backgroundColor: "rgba(245, 243, 240, 0.8)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.08)",
    padding: 14,
    marginTop: 4,
  },
  commentText: {
    fontSize: 14,
    lineHeight: 22,
    color: "#5C4A32",
    fontFamily: baseFontFamily,
  },
  // 다시 검색하기 버튼
  searchAgainButton: {
    backgroundColor: "#4A90E2",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 24,
  },
  searchAgainButtonText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
});
