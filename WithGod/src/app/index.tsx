import { baseFontFamily } from '@/shared/styles';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

export default function SplashScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      router.replace('/(tabs)');
    }, 3000);

    return () => clearTimeout(timeoutId);
  }, [router]);

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={['#4A90E2', '#4FA3EE', '#5EB2F8']}
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
              accessibilityLabel="신과함께 앱 로고"
            />
          </View>
          <Text style={styles.title}>신과함께</Text>
          <Text style={styles.subtitle}>당신의 마음에 위로를 전해요</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#4A90E2',
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
    fontSize: 36,
    fontWeight: '800',
    lineHeight: 40,
    letterSpacing: 5.4,
    color: '#FFFFFF',
    textAlign: 'center',
    fontFamily: baseFontFamily,
  },
  subtitle: {
    marginTop: 12,
    fontSize: 16,
    lineHeight: 24,
    color: 'rgba(255, 255, 255, 0.9)',
    textAlign: 'center',
    fontFamily: baseFontFamily,
  },
});

