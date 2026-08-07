import { applyPendingUpdateAsync, type OtaPhase } from '@/shared/lib/otaUpdate';
import { baseFontFamily, colors, scaleFont } from '@/shared/styles';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { useFocusEffect, useNavigation, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

// 콜드 스타트에서 스플래시가 한 번 재생됐는지 (프로세스 생존 동안 유지).
// 위젯 탭 등 '/' 딥링크는 실행 중인 앱의 스택을 [탭, 스플래시]로 리셋하므로,
// 이 플래그가 없으면 앱이 새로 켜지는 것처럼 스플래시가 또 재생된다.
let splashPlayedThisLaunch = false;

/** 스플래시 최소 노출 시간. OTA 확인은 이 시간 안에서 끝내는 것을 목표로 한다. */
const SPLASH_MIN_MS = 3000;

export default function SplashScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const timerElapsedRef = useRef(false);
  const isRelaunch = useRef(splashPlayedThisLaunch).current;
  const [otaPhase, setOtaPhase] = useState<OtaPhase>('idle');

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
    splashPlayedThisLaunch = true;
  }, []);

  // 재진입 시 홈 탭으로 전환하는 안전망. 1차 방어는 +native-intent(스플래시
  // 라우트 마운트 자체를 차단)이고, 여기는 다른 경로로 '/'에 재진입한 경우만
  // 처리한다. 마운트 커밋 중(useLayoutEffect)의 팝 디스패치는 네이티브 스택
  // 전환과 경합해 크래시했으므로(#16), 마운트가 끝난 뒤 태스크로 미뤄서 보낸다.
  useEffect(() => {
    if (!isRelaunch) return;
    const timeoutId = setTimeout(() => {
      router.navigate('/(tabs)');
    }, 0);
    return () => clearTimeout(timeoutId);
  }, [isRelaunch, router]);

  // 스플래시가 머무는 동안 OTA 새 번들이 있으면 받아서 곧바로 재시작한다.
  // 사용자가 앱을 껐다 켜지 않아도 새 버전 화면으로 들어가게 하기 위함이고,
  // 어차피 기다리는 3초 안에서 처리하므로 체감 지연이 없다.
  // 확인·내려받기가 실패하거나 늦어지면 그냥 원래대로 진행한다(fail-open).
  useEffect(() => {
    if (isRelaunch) return;
    let cancelled = false;

    const minWait = new Promise<void>((resolve) => {
      setTimeout(resolve, SPLASH_MIN_MS);
    });

    void (async () => {
      const reloading = await applyPendingUpdateAsync((phase) => {
        if (!cancelled) setOtaPhase(phase);
      });
      // 재시작이 걸렸으면 화면을 넘기지 않는다 — 곧 새 번들로 앱이 다시 뜬다.
      if (reloading || cancelled) return;

      await minWait;
      if (cancelled) return;
      timerElapsedRef.current = true;
      // 푸시 딥링크 등으로 다른 화면이 이미 위에 떠 있으면 back() 이 그 화면을
      // 팝해버리므로, 스플래시가 최상단(포커스)일 때만 닫는다.
      if (navigation.isFocused()) {
        dismissSplash();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isRelaunch, navigation, dismissSplash]);

  // 딥링크 화면에서 돌아와 스플래시가 다시 보이면(타이머는 이미 소진) 즉시 닫는다.
  useFocusEffect(
    useCallback(() => {
      if (timerElapsedRef.current) {
        dismissSplash();
      }
    }, [dismissSplash])
  );

  if (isRelaunch) {
    return null;
  }

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
          <Text style={styles.subtitle}>
            {otaPhase === 'downloading'
              ? t('splash.updating')
              : t('splash.subtitle')}
          </Text>
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
