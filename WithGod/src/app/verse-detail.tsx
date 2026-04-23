import { Image } from 'expo-image';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { baseFontFamily, scaleFont } from '@/shared/styles';

const BACK_ICON = require('../shared/assets/images/chevron-right.png');

const getSingleParam = (value: string | string[] | undefined): string => {
  if (Array.isArray(value)) {
    return value[0] ?? '';
  }
  return value ?? '';
};

export default function VerseDetailScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{
    ref?: string | string[];
    text?: string | string[];
    comment?: string | string[];
    tag?: string | string[];
    title?: string | string[];
    body?: string | string[];
  }>();

  const ref = getSingleParam(params.ref);
  const text = getSingleParam(params.text);
  const comment = getSingleParam(params.comment);
  const tag = getSingleParam(params.tag);
  const title = getSingleParam(params.title);
  const body = getSingleParam(params.body);

  const hasVerseContent = !!(ref || text || comment || tag);

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right']}>
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <Image source={BACK_ICON} style={styles.backIcon} contentFit="contain" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>말씀 상세</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {(title || body) && (
          <View style={styles.noticeCard}>
            {title ? <Text style={styles.noticeTitle}>{title}</Text> : null}
            {body ? <Text style={styles.noticeBody}>{body}</Text> : null}
          </View>
        )}

        {hasVerseContent ? (
          <View style={styles.verseCard}>
            {text ? (
              <Text style={styles.verseText}>
                {'"'}
                {text}
                {'"'}
              </Text>
            ) : null}
            {ref ? <Text style={styles.verseReference}>{ref}</Text> : null}
            {tag ? (
              <View style={styles.tagRow}>
                <View style={styles.tag}>
                  <Text style={styles.tagText}>{tag}</Text>
                </View>
              </View>
            ) : null}
            {comment ? (
              <View style={styles.commentBubble}>
                <Text style={styles.commentText}>{comment}</Text>
              </View>
            ) : null}
          </View>
        ) : (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>표시할 말씀 정보가 없어요</Text>
            <Text style={styles.emptyDescription}>
              푸시 payload에 `ref`, `text`, `comment`, `tag` 또는 `url`을 담아주세요.
            </Text>
          </View>
        )}

        <TouchableOpacity
          style={styles.homeButton}
          activeOpacity={0.7}
          onPress={() => router.replace('/(tabs)')}
        >
          <Text style={styles.homeButtonText}>홈으로 돌아가기</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    paddingHorizontal: 16,
    paddingBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
  },
  backButton: {
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  backIcon: {
    width: 8,
    height: 14,
    transform: [{ rotate: '180deg' }],
    tintColor: '#101828',
  },
  headerTitle: {
    flex: 1,
    fontSize: scaleFont(18),
    lineHeight: scaleFont(24),
    fontWeight: '600',
    color: '#101828',
    fontFamily: baseFontFamily,
  },
  headerSpacer: {
    width: 32,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 24,
    gap: 16,
  },
  noticeCard: {
    backgroundColor: '#E7F0FF',
    borderRadius: 16,
    padding: 18,
  },
  noticeTitle: {
    fontSize: scaleFont(18),
    lineHeight: scaleFont(24),
    fontWeight: '600',
    color: '#1E2939',
    fontFamily: baseFontFamily,
    marginBottom: 6,
  },
  noticeBody: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(22),
    color: '#475467',
    fontFamily: baseFontFamily,
  },
  verseCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(139, 115, 85, 0.1)',
    padding: 20,
    shadowColor: '#8B7355',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  verseText: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(32),
    color: '#1E2939',
    marginBottom: 10,
    fontFamily: baseFontFamily,
  },
  verseReference: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(22),
    fontWeight: '600',
    color: '#4A90E2',
    fontFamily: baseFontFamily,
    marginBottom: 10,
  },
  tagRow: {
    alignSelf: 'flex-end',
    marginBottom: 12,
  },
  tag: {
    backgroundColor: 'rgba(106, 114, 130, 0.1)',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  tagText: {
    fontSize: scaleFont(12),
    lineHeight: scaleFont(18),
    fontWeight: '600',
    color: '#6A7282',
    fontFamily: baseFontFamily,
  },
  commentBubble: {
    backgroundColor: 'rgba(245, 243, 240, 0.8)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(139, 115, 85, 0.08)',
    padding: 16,
  },
  commentText: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: '#5C4A32',
    fontFamily: baseFontFamily,
  },
  emptyCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  emptyTitle: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(24),
    fontWeight: '600',
    color: '#101828',
    fontFamily: baseFontFamily,
    marginBottom: 8,
  },
  emptyDescription: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(22),
    color: '#6A7282',
    fontFamily: baseFontFamily,
  },
  homeButton: {
    backgroundColor: '#4A90E2',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
  },
  homeButtonText: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(22),
    fontWeight: '600',
    color: '#FFFFFF',
    fontFamily: baseFontFamily,
  },
});
