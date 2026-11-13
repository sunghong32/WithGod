import { Platform } from 'react-native';
import type * as ApplicationModule from 'expo-application';
import type * as SecureStoreModule from 'expo-secure-store';

/**
 * 앱을 지워도 남는 곳에서 익명 기기 ID 를 되찾는다(#79).
 *
 * 익명 ID 는 지표(anon_id)와 푸시 기기 등록(device_id)이 같이 쓴다. 앱 문서 폴더의
 * 파일에만 두면 앱을 지울 때 같이 지워져, 다시 깐 사람이 새 사용자·새 푸시 기기로 잡힌다.
 *
 * - iOS: 키체인(expo-secure-store)에도 둔다. 키체인 항목은 앱을 지워도 남아, 다시 깔면
 *   같은 ID 를 되찾는다. AFTER_FIRST_UNLOCK 이라 백업으로 새 아이폰에 옮겨도 이어진다.
 * - Android: 앱 전용 ANDROID_ID(서명 키·사용자·기기마다 다른 값)를 해시해 만든다.
 *   같은 폰이면 다시 깔아도 같고, 공장 초기화하면 바뀐다. 원래 값은 내보내지 않는다.
 *
 * 두 모듈 모두 네이티브라 1.6.x 이하 바이너리에는 없다. 그 바이너리로 가는 OTA 에서 모듈
 * JS 를 그냥 불러오면 requireNativeModule 이 던져 앱이 죽으므로, 네이티브 모듈이 있는지
 * 먼저 보고 없으면 아무것도 하지 않는다(지금처럼 파일에만 둔다). modules/widget-bridge 와 같은 방식.
 */

const KEYCHAIN_KEY = 'withgod.deviceId';

const hasNativeModule = (name: string): boolean => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 모듈 미탑재 바이너리 폴백
    const { requireOptionalNativeModule } = require('expo-modules-core');
    return requireOptionalNativeModule(name) != null;
  } catch {
    return false;
  }
};

let secureStore: typeof SecureStoreModule | null | undefined;

const loadSecureStore = (): typeof SecureStoreModule | null => {
  if (secureStore === undefined) {
    secureStore =
      Platform.OS === 'ios' && hasNativeModule('ExpoSecureStore')
        ? // eslint-disable-next-line @typescript-eslint/no-require-imports -- 네이티브 모듈을 확인한 뒤에만 불러온다
          (require('expo-secure-store') as typeof SecureStoreModule)
        : null;
  }
  return secureStore;
};

const keychainOptions = (
  store: typeof SecureStoreModule,
): SecureStoreModule.SecureStoreOptions => ({
  keychainAccessible: store.AFTER_FIRST_UNLOCK,
});

/** 53비트 문자열 해시(cyrb53). 암호용이 아니라 ID 를 고르게 펴는 용도다. */
const cyrb53 = (value: string, seed: number): number => {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < value.length; i += 1) {
    const ch = value.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 4294967296 * (2097151 & h2) + (h1 >>> 0);
};

export const hashForDeviceId = (value: string): string =>
  [1, 2]
    .map((seed) => cyrb53(`withgod:${value}`, seed).toString(16).padStart(14, '0'))
    .join('');

const androidDeviceId = (): string | null => {
  if (!hasNativeModule('ExpoApplication')) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 네이티브 모듈을 확인한 뒤에만 불러온다
    const { getAndroidId } = require('expo-application') as typeof ApplicationModule;
    const raw = getAndroidId();
    return raw ? `dev-a-${hashForDeviceId(raw)}` : null;
  } catch {
    return null;
  }
};

/**
 * 앱을 새로 깔아 파일에 ID 가 없을 때 부른다. 예전에 쓰던 ID(iOS)나 이 기기에서
 * 늘 같은 ID(Android)를 돌려준다. 되찾을 수 없으면 null — 그때는 새로 만든다.
 */
export const recallDeviceId = async (): Promise<string | null> => {
  if (Platform.OS === 'android') return androidDeviceId();
  const store = loadSecureStore();
  if (!store) return null;
  try {
    return (await store.getItemAsync(KEYCHAIN_KEY, keychainOptions(store))) || null;
  } catch {
    return null;
  }
};

/**
 * 지금 쓰는 ID 를 앱을 지워도 남는 곳에 둔다(iOS 키체인). 업데이트로 이 코드를 처음 받은
 * 기존 사용자도 여기서 키체인에 옮겨져, 그다음 재설치부터 같은 ID 를 되찾는다.
 * Android 는 ANDROID_ID 에서 매번 다시 만들 수 있어 둘 곳이 없다.
 */
export const rememberDeviceId = async (id: string): Promise<void> => {
  const store = loadSecureStore();
  if (!store) return;
  try {
    const saved = await store.getItemAsync(KEYCHAIN_KEY, keychainOptions(store));
    if (saved !== id) {
      await store.setItemAsync(KEYCHAIN_KEY, id, keychainOptions(store));
    }
  } catch {
    // 키체인 실패가 앱 흐름을 막지 않는다 — 파일의 ID 는 그대로 쓴다.
  }
};
