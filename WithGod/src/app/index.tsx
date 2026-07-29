import { baseFontFamily, colors, scaleFont } from '@/shared/styles';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { useFocusEffect, useNavigation, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

export default function SplashScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const timerElapsedRef = useRef(false);

  const dismissSplash = useCallback(() => {
    // anchor='(tabs)' 로 인해 스택이 [(tabs), index] 이므로, replace 를 하면
    // (tabs) 가 하나 더 쌓여 중복된다. 밑의 (tabs) 로 pop 해서 중복을 방지한다.
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/(tabs)');
    }
  }, [router]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      timerElapsedRef.current = true;
      // 푸시 딥링크 등으로 다른 화면이 이미 위에 떠 있으면 back() 이 그 화면을
      // 팝해버리므로, 스플래시가 최상단(포커스)일 때만 닫는다.
      if (navigation.isFocused()) {
        dismissSplash();
      }
    }, 3000);

    return () => clearTimeout(timeoutId);
  }, [navigation, dismissSplash]);

  // 딥링크 화면에서 돌아와 스플래시가 다시 보이면(타이머는 이미 소진) 즉시 닫는다.
  useFocusEffect(
    useCallback(() => {
      if (timerElapsedRef.current) {
        dismissSplash();
      }
    }, [dismissSplash])
  );

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={[colors.primary, '#4FA3EE', '#5EB2F8']}
        locations={[0, 0.55, 1]}
        start={{ x: 0.2, y: 0 }}
        end={{ x: 0.8, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      <LinearGradient
        colors={['rgba(255, 255, 255, 0.25)', 'rgba(94, 178, 248, 0)']}
        locations={[0, 1]}
        start={{ x: 0.5, y: 0.15 }}
        end={{ x: 0.5, y: 0.9 }}
        pointerEvents="none"
        style={styles.highlight}
      />
      <SafeAreaView
        style={[
          styles.safeArea,
          {
            paddingTop: insets.top,
            paddingBottom: insets.bottom,
          },
        ]}
        edges={['left', 'right']}
      >
        <View style={styles.container}>
          <View style={styles.logoWrapper}>
            <Image
              source={require('@/shared/assets/images/Logo.png')}
              style={styles.logo}
              contentFit="contain"
              accessibilityLabel={t('splash.logoA11y')}
            />
          </View>
          <Text style={styles.title}>{t('common.appName')}</Text>
          <Text style={styles.subtitle}>{t('splash.subtitle')}</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.primary,
  },
  safeArea: {
    flex: 1,
  },
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  highlight: {
    ...StyleSheet.absoluteFillObject,
    opacity: 0.4,
  },
  logoWrapper: {
    backgroundColor: '#FFFFFF',
    borderRadius: 32,
    height: 128,
    width: 128,
    paddingTop: 6,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.12,
    shadowRadius: 40,
    elevation: 12,
  },
  logo: {
    height: '100%',
    width: '100%',
  },
  title: {
    marginTop: 32,
    fontSize: scaleFont(36),
    fontWeight: '800',
    lineHeight: scaleFont(40),
    letterSpacing: 5.4,
    color: '#FFFFFF',
    textAlign: 'center',
    fontFamily: baseFontFamily,
  },
  subtitle: {
    marginTop: 12,
    fontSize: scaleFont(16),
    lineHeight: scaleFont(24),
    color: 'rgba(255, 255, 255, 0.9)',
    textAlign: 'center',
    fontFamily: baseFontFamily,
  },
});
