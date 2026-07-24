import axios from 'axios';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * 앱 업데이트 확인.
 *
 * 서버(GET /app-version)에 최신/최소지원 버전을 물어보고 현재 버전과 비교한다.
 * - 현재 < 최소지원 → 강제 업데이트(계속 쓰려면 업데이트 필수)
 * - 현재 < 최신     → 선택 업데이트(권장, 나중에 가능)
 * - 그 외           → 없음
 *
 * 서버가 응답하지 않으면 아무것도 안 한다(fail-open) — 서버 문제로 앱이 막히면
 * 안 되기 때문이다.
 */

const VERSION_ENDPOINT = 'https://mincha.co.kr/app-version';
const TIMEOUT_MS = 5000;

interface AppVersionConfig {
  latest: string;
  min_supported: string;
  ios_url: string;
  android_url: string;
}

export type UpdateStatus =
  | { type: 'none' }
  | { type: 'optional'; storeUrl: string }
  | { type: 'forced'; storeUrl: string };

/** semver 비교. a<b → -1, a==b → 0, a>b → 1. */
export const compareVersions = (a: string, b: string): number => {
  const pa = a.split('.').map((n) => parseInt(n, 10) || 0);
  const pb = b.split('.').map((n) => parseInt(n, 10) || 0);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const diff = (pa[i] || 0) - (pb[i] || 0);
    if (diff !== 0) return diff > 0 ? 1 : -1;
  }
  return 0;
};

export const checkForUpdate = async (): Promise<UpdateStatus> => {
  if (Platform.OS === 'web') return { type: 'none' };

  try {
    const current = Constants.expoConfig?.version || Constants.nativeAppVersion || '0.0.0';
    const { data } = await axios.get<AppVersionConfig>(VERSION_ENDPOINT, {
      timeout: TIMEOUT_MS,
    });
    if (!data || typeof data.latest !== 'string') return { type: 'none' };

    const storeUrl = Platform.OS === 'ios' ? data.ios_url : data.android_url;
    if (!storeUrl) return { type: 'none' };

    if (data.min_supported && compareVersions(current, data.min_supported) < 0) {
      return { type: 'forced', storeUrl };
    }
    if (compareVersions(current, data.latest) < 0) {
      return { type: 'optional', storeUrl };
    }
    return { type: 'none' };
  } catch {
    // 서버 미응답·오류 시 앱을 막지 않는다.
    return { type: 'none' };
  }
};
