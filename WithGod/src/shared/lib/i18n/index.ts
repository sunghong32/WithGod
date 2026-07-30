/* eslint-disable import/no-named-as-default-member --
   i18next 는 싱글턴 인스턴스(default export)의 메서드를 쓰는 게 공식 패턴이다.
   named import 로 바꾸면 인스턴스 바인딩 의도가 흐려져 규칙을 이 파일만 끈다. */
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import { getStorageItem, removeStorageItem, setStorageItem } from '@/shared/lib/storage';

import de from './locales/de.json';
import en from './locales/en.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import it from './locales/it.json';
import ko from './locales/ko.json';
import pl from './locales/pl.json';
import pt from './locales/pt.json';

/**
 * 앱 다국어(i18n).
 *
 * - i18next + react-i18next 는 순수 JS 라 OTA 로도 언어 리소스를 갱신할 수 있다.
 * - 기기 언어 감지는 Hermes 의 Intl 로 한다(네이티브 모듈 불필요).
 * - 번역이 준비돼도 품질 검증 전에는 사용자에게 노출하지 않도록
 *   **활성 언어 게이트**를 둔다. 게이트에 없는 기기 언어는 폴백을 따른다.
 *   현재는 ko 만 활성 — 서버 스위치(이슈 #10)가 붙으면 서버 값으로 대체된다.
 * - 모듈 로드 시점에 동기로 초기화해 위젯 태스크 등 React 밖에서도 안전하다.
 */

export const SUPPORTED_LANGUAGES = ['ko', 'en', 'es', 'pt', 'de', 'fr', 'it', 'pl'] as const;
export type AppLanguage = (typeof SUPPORTED_LANGUAGES)[number];

// 품질 검증(이슈 #11 저지 파이프라인)을 통과해 사용자에게 노출하는 언어.
// 2026-07-29 전 언어 오픈(v1.3.0) — 서버 enabled_languages 스위치와 함께 켠다.
const ENABLED_LANGUAGES: readonly AppLanguage[] = [...SUPPORTED_LANGUAGES];

const LANGUAGE_KEY = 'withgod.language';
// 검증·개발용: 게이트를 무시하고 강제할 언어 (일반 사용자 경로에서는 쓰지 않음)
const DEV_LANGUAGE_KEY = 'withgod.language.dev';

const isSupported = (value: unknown): value is AppLanguage =>
  typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value);

/**
 * 기기 언어의 원시 태그(ko-KR 등)에서 기본 언어(ko)만 뽑는다.
 *
 * iOS 의 Intl 은 '기기 언어'가 아니라 '앱이 선언한 지원 언어와 협상된 결과'를
 * 돌려준다 — 지원 언어 선언(app.json locales)이 없던 v1.3.0 에서 한국어 기기가
 * 영어로 협상되는 버그의 원인. expo-localization 은 사용자의 실제 선호 언어를
 * 반환하므로 이를 우선하고, 네이티브 모듈이 없는 환경(구 dev client 등)에서만
 * Intl 로 폴백한다.
 */
export const detectDeviceLanguage = (): string => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 모듈 미탑재 환경 폴백을 위해 지연 로드
    const { getLocales } = require('expo-localization') as typeof import('expo-localization');
    const code = getLocales()[0]?.languageCode ?? '';
    if (code) return code.toLowerCase();
  } catch {
    // expo-localization 미탑재 — Intl 폴백
  }
  try {
    const tag = Intl.DateTimeFormat().resolvedOptions().locale || '';
    return tag.split('-')[0].toLowerCase();
  } catch {
    return '';
  }
};

/**
 * 실제 사용할 언어 결정: 저장된 선택 → 기기 언어 → en → ko.
 * 각 단계에서 활성 게이트를 통과해야 한다.
 */
const resolveLanguage = (stored: string | null): AppLanguage => {
  if (isSupported(stored) && ENABLED_LANGUAGES.includes(stored)) return stored;
  const device = detectDeviceLanguage();
  if (isSupported(device) && ENABLED_LANGUAGES.includes(device)) return device;
  if (ENABLED_LANGUAGES.includes('en')) return 'en';
  return 'ko';
};

// 동기 초기화 — 첫 렌더·위젯 태스크가 즉시 t() 를 쓸 수 있어야 한다.
// 언어는 일단 ko 로 시작하고, initAppLanguage() 가 저장값·기기값으로 보정한다.
void i18next.use(initReactI18next).init({
  resources: {
    ko: { translation: ko },
    en: { translation: en },
    es: { translation: es },
    pt: { translation: pt },
    de: { translation: de },
    fr: { translation: fr },
    it: { translation: it },
    pl: { translation: pl },
  },
  lng: 'ko',
  fallbackLng: 'ko',
  interpolation: { escapeValue: false },
  returnNull: false,
  // 리소스가 번들에 포함돼 있으므로 동기 초기화(v26: initAsync) — 첫 렌더 전에 준비된다.
  initAsync: false,
});

/** 앱 시작 시 1회: 저장된 선택/기기 언어를 반영한다. 실패해도 ko 로 동작. */
export const initAppLanguage = async (): Promise<void> => {
  try {
    // 개발·검증용 강제 언어가 있으면 게이트를 무시하고 그대로 쓴다.
    const dev = await getStorageItem(DEV_LANGUAGE_KEY);
    if (isSupported(dev)) {
      await i18next.changeLanguage(dev);
      return;
    }
    const stored = await getStorageItem(LANGUAGE_KEY);
    const resolved = resolveLanguage(stored);
    if (resolved !== i18next.language) {
      await i18next.changeLanguage(resolved);
    }
  } catch {
    // 언어 결정 실패가 앱을 막지 않는다 — ko 유지.
  }
};

/** 설정에서 수동 변경 시: 저장하고 즉시 적용. */
export const setAppLanguage = async (language: AppLanguage): Promise<void> => {
  await setStorageItem(LANGUAGE_KEY, language);
  await i18next.changeLanguage(language);
};

/** 언어 선택 UI 의 선택값: 'system'(기기 언어 따르기) 또는 특정 언어. */
export type AppLanguageChoice = AppLanguage | 'system';

/** 저장된 선택을 읽는다 — 없으면 'system'(기기 언어 따르기). */
export const getAppLanguageChoice = async (): Promise<AppLanguageChoice> => {
  try {
    const stored = await getStorageItem(LANGUAGE_KEY);
    return isSupported(stored) ? stored : 'system';
  } catch {
    return 'system';
  }
};

/** 선택 적용: 'system'이면 저장을 지우고 기기 언어로 재결정한다. */
export const setAppLanguageChoice = async (
  choice: AppLanguageChoice,
): Promise<void> => {
  if (choice === 'system') {
    await removeStorageItem(LANGUAGE_KEY);
    await i18next.changeLanguage(resolveLanguage(null));
    return;
  }
  await setAppLanguage(choice);
};

/** 언어 선택 UI 표기용 — 각 언어의 자기 이름(번역하지 않는 것이 관례). */
export const LANGUAGE_NATIVE_NAMES: Record<AppLanguage, string> = {
  ko: '한국어',
  en: 'English',
  es: 'Español',
  pt: 'Português',
  de: 'Deutsch',
  fr: 'Français',
  it: 'Italiano',
  pl: 'Polski',
};

export const getAppLanguage = (): string => i18next.language;

/** React 컴포넌트 밖(에러 메시지·푸시·위젯 등)에서 쓰는 번역 함수. */
export const t = i18next.t.bind(i18next);

export default i18next;
