import { Platform } from 'react-native';
import {
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from 'expo-file-system/legacy';

/**
 * 경량 영속 저장소.
 *
 * AsyncStorage 는 네이티브 모듈 추가가 필요해 (프로젝트 정책상 신규 네이티브
 * 의존성 금지) 이미 설치된 expo-file-system 으로 키-값을 영속화한다.
 * - 네이티브: documentDirectory 하위 JSON 파일에 저장
 * - 웹: localStorage 폴백
 *
 * 단순한 설정값(알림 on/off, 알림 시각, device_id) 정도만 다루므로
 * 메모리 캐시 + 단일 JSON 파일로 충분하다.
 */

const STORAGE_FILE = 'withgod-storage.json';
const isWeb = Platform.OS === 'web';

let memoryCache: Record<string, string> | null = null;

const getFileUri = (): string | null => {
  if (!documentDirectory) return null;
  return `${documentDirectory}${STORAGE_FILE}`;
};

const loadAll = async (): Promise<Record<string, string>> => {
  if (memoryCache) return memoryCache;

  if (isWeb) {
    memoryCache = {};
    try {
      if (typeof localStorage !== 'undefined') {
        const raw = localStorage.getItem(STORAGE_FILE);
        if (raw) memoryCache = JSON.parse(raw) as Record<string, string>;
      }
    } catch (error) {
      if (__DEV__) console.warn('[Storage] Failed to load (web)', error);
    }
    return memoryCache;
  }

  const uri = getFileUri();
  if (!uri) {
    memoryCache = {};
    return memoryCache;
  }

  try {
    const info = await getInfoAsync(uri);
    if (info.exists) {
      const raw = await readAsStringAsync(uri);
      memoryCache = raw ? (JSON.parse(raw) as Record<string, string>) : {};
    } else {
      memoryCache = {};
    }
  } catch (error) {
    if (__DEV__) console.warn('[Storage] Failed to load', error);
    memoryCache = {};
  }
  return memoryCache;
};

const persist = async (data: Record<string, string>): Promise<void> => {
  const serialized = JSON.stringify(data);

  if (isWeb) {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_FILE, serialized);
      }
    } catch (error) {
      if (__DEV__) console.warn('[Storage] Failed to persist (web)', error);
    }
    return;
  }

  const uri = getFileUri();
  if (!uri) return;
  try {
    await writeAsStringAsync(uri, serialized);
  } catch (error) {
    if (__DEV__) console.warn('[Storage] Failed to persist', error);
  }
};

export const getStorageItem = async (key: string): Promise<string | null> => {
  const data = await loadAll();
  return key in data ? data[key] : null;
};

export const setStorageItem = async (
  key: string,
  value: string,
): Promise<void> => {
  const data = await loadAll();
  data[key] = value;
  memoryCache = data;
  await persist(data);
};

export const removeStorageItem = async (key: string): Promise<void> => {
  const data = await loadAll();
  if (key in data) {
    delete data[key];
    memoryCache = data;
    await persist(data);
  }
};
