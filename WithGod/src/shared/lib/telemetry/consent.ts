import { getStorageItem, setStorageItem } from '@/shared/lib/storage';

/**
 * 통계 수집 동의 상태.
 *
 * - 유럽(EU/EEA)은 GDPR상 명시적 동의 전에는 수집할 수 없다(opt-in). 그래서
 *   해당 지역은 첫 실행 때 동의를 받고, 동의 전까지 수집하지 않는다.
 * - 그 외 지역은 기본 수집(opt-out)하되, 설정에서 언제든 끌 수 있다.
 * - 어느 지역이든 '끄기'(철회)가 가능해야 한다는 GDPR 요건을 위해 설정 토글은
 *   항상 남긴다.
 */

const CONSENT_KEY = 'withgod.telemetry.consent'; // 'granted' | 'denied'
const LEGACY_ENABLED_KEY = 'withgod.telemetry.enabled'; // 구버전: '1' | '0'

export type ConsentState = 'granted' | 'denied' | 'undecided';

// 지역 판단은 타임존으로 한다(새 네이티브 의존성 없이 가능). 대부분의 EEA 는
// Europe/* 이고, 대서양의 몇 개 지역만 예외로 따로 담는다.
const EEA_TIMEZONE_EXCEPTIONS: ReadonlySet<string> = new Set([
  'Atlantic/Reykjavik', // 아이슬란드
  'Atlantic/Canary', // 스페인(카나리아)
  'Atlantic/Madeira', // 포르투갈(마데이라)
  'Atlantic/Azores', // 포르투갈(아조레스)
]);

/**
 * 명시적 동의가 필요한 지역(EU/EEA)인지.
 *
 * 판단이 애매하면(타임존 불명·오류) 안전하게 '필요함'으로 본다 — 유럽 사용자를
 * 실수로 동의 없이 추적하는 것보다, 유럽 아닌 사용자에게 한 번 더 묻는 편이 낫다.
 */
export const isConsentRequiredRegion = (): boolean => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!tz) return true;
    if (tz.startsWith('Europe/')) return true;
    return EEA_TIMEZONE_EXCEPTIONS.has(tz);
  } catch {
    return true;
  }
};

export const readConsent = async (): Promise<ConsentState> => {
  const value = await getStorageItem(CONSENT_KEY);
  if (value === 'granted') return 'granted';
  if (value === 'denied') return 'denied';

  // 구버전(설정 토글만 있던 빌드)에서 이미 결정한 사용자의 선택을 존중한다.
  const legacy = await getStorageItem(LEGACY_ENABLED_KEY);
  if (legacy === '0') return 'denied';
  if (legacy === '1') return 'granted';

  return 'undecided';
};

export const writeConsent = async (granted: boolean): Promise<void> => {
  await setStorageItem(CONSENT_KEY, granted ? 'granted' : 'denied');
  // 구버전 키도 함께 맞춰, 이 빌드/구빌드를 오가도 상태가 어긋나지 않게 한다.
  await setStorageItem(LEGACY_ENABLED_KEY, granted ? '1' : '0');
};

/**
 * 저장된 동의와 지역을 종합해, 이번 실행에서 수집을 켤지 결정한다.
 * - granted → 켬 / denied → 끔
 * - undecided → 유럽이면 끔(동의 대기), 그 외 지역이면 켬(기본 수집)
 */
export const resolveEnabled = (consent: ConsentState): boolean => {
  if (consent === 'granted') return true;
  if (consent === 'denied') return false;
  return !isConsentRequiredRegion();
};

/** 첫 실행 동의창을 띄워야 하는지: 아직 결정 안 했고, 동의가 필요한 지역일 때. */
export const needsConsentPrompt = async (): Promise<boolean> => {
  const consent = await readConsent();
  return consent === 'undecided' && isConsentRequiredRegion();
};
