import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Platform, StyleSheet, Text, View } from 'react-native';

export default function HomeScreen() {
  return (
    <View style={styles.container}>
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
      <View style={styles.content}>
        <View style={styles.logoGroup}>
          <View style={styles.logoWrapper}>
            <Image
              source={require('@/shared/assets/images/Logo.png')}
              style={styles.logo}
              contentFit="contain"
              accessibilityLabel="WithGod 앱 로고"
            />
          </View>
          <Text style={styles.title}>WithGod</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#4A90E2',
  },
  highlight: {
    ...StyleSheet.absoluteFillObject,
    opacity: 0.4,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoGroup: {
    alignItems: 'center',
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
    textTransform: 'none',
    textAlign: 'center',
    fontFamily: Platform.select({
      ios: 'System',
      android: 'Roboto',
      default: 'sans-serif',
    }),
  },
});
