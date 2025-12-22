import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { verseApi } from "@/features/verse";

const LOGO_IMAGE = require("../shared/assets/images/Logo.png");
const BACK_ICON = require("../shared/assets/images/chevron-right.png");

const baseFontFamily = Platform.select({
  ios: "System",
  android: "Roboto",
  web: "sans-serif",
  default: "sans-serif",
});

export default function ResultScreen() {
  const router = useRouter();
  const { mood } = useLocalSearchParams<{ mood: string }>();
  const insets = useSafeAreaInsets();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["verse", "recommend", mood],
    queryFn: () => verseApi.getRecommendation({ mood: mood ?? "" }),
    enabled: !!mood,
  });

  const headerPaddingTop = Platform.OS === "android"
    ? (StatusBar.currentHeight ?? 0) + 12
    : insets.top + 12;

  const result = data?.results?.[0];

  return (
    <View style={styles.container}>
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
        <View style={styles.headerLogoWrapper}>
          <Image
            source={LOGO_IMAGE}
            style={styles.headerLogo}
            contentFit="contain"
            accessibilityLabel="신과함께 로고"
          />
        </View>
        <Text style={styles.headerTitle}>신과함께</Text>
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.moodCard}>
          <Text style={styles.moodLabel}>당신의 마음</Text>
          <Text style={styles.moodText}>{mood}</Text>
        </View>

        <View style={styles.resultCard}>
          <View style={styles.resultHeader}>
            <View style={styles.resultAccent} />
            <Text style={styles.resultTitle}>위로의 말씀</Text>
          </View>

          {isLoading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#4A90E2" />
              <Text style={styles.loadingText}>말씀을 찾고 있어요...</Text>
            </View>
          ) : isError ? (
            <TouchableOpacity style={styles.errorContainer} onPress={() => refetch()}>
              <Text style={styles.errorText}>
                말씀을 불러오지 못했어요.{"\n"}탭하여 다시 시도해주세요.
              </Text>
            </TouchableOpacity>
          ) : result ? (
            <View style={styles.verseContainer}>
              <Text style={styles.verseText}>{result.text}</Text>
              <Text style={styles.verseReference}>{result.ref}</Text>
              {result.comment && (
                <View style={styles.commentContainer}>
                  <Text style={styles.commentText}>{result.comment}</Text>
                </View>
              )}
            </View>
          ) : null}
        </View>

        <TouchableOpacity
          style={styles.homeButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <Text style={styles.homeButtonText}>처음으로 돌아가기</Text>
        </TouchableOpacity>
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
    paddingHorizontal: 24,
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
  headerLogoWrapper: {
    height: 40,
    width: 40,
    borderRadius: 20,
    backgroundColor: "#E7F0FF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  headerLogo: {
    height: 28,
    width: 28,
  },
  headerTitle: {
    fontSize: 24,
    lineHeight: 32,
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 32,
  },
  moodCard: {
    backgroundColor: "#E7F0FF",
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
  },
  moodLabel: {
    fontSize: 14,
    color: "#4A90E2",
    fontWeight: "600",
    marginBottom: 8,
    fontFamily: baseFontFamily,
  },
  moodText: {
    fontSize: 18,
    lineHeight: 26,
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  resultCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 24,
    marginBottom: 32,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },
  resultAccent: {
    height: 24,
    width: 4,
    borderRadius: 999,
    backgroundColor: "#4A90E2",
    marginRight: 8,
  },
  resultTitle: {
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  loadingContainer: {
    alignItems: "center",
    paddingVertical: 40,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
  errorContainer: {
    alignItems: "center",
    paddingVertical: 40,
  },
  errorText: {
    fontSize: 16,
    color: "#6A7282",
    textAlign: "center",
    lineHeight: 24,
    fontFamily: baseFontFamily,
  },
  verseContainer: {
    gap: 16,
  },
  verseText: {
    fontSize: 20,
    lineHeight: 32,
    color: "#1E2939",
    fontFamily: baseFontFamily,
  },
  verseReference: {
    fontSize: 16,
    fontWeight: "600",
    color: "#4A90E2",
    fontFamily: baseFontFamily,
  },
  commentContainer: {
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  commentText: {
    fontSize: 16,
    lineHeight: 26,
    color: "#4A5565",
    fontFamily: baseFontFamily,
  },
  homeButton: {
    backgroundColor: "#4A90E2",
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
  },
  homeButtonText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
});
