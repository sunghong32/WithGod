import Animated from 'react-native-reanimated';

import { scaleFont } from '@/shared/styles';

export function HelloWave() {
  return (
    <Animated.Text
      style={{
        fontSize: scaleFont(28),
        lineHeight: scaleFont(32),
        marginTop: -6,
        animationName: {
          '50%': { transform: [{ rotate: '25deg' }] },
        },
        animationIterationCount: 4,
        animationDuration: '300ms',
      }}>
      👋
    </Animated.Text>
  );
}
