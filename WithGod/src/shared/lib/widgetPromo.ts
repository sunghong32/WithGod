import { getStorageItem, setStorageItem } from './storage';

/**
 * 홈 화면 위젯 기능 안내(1회성 배너)의 노출 여부 플래그.
 * 배너를 닫거나 안내를 확인하면 다시 노출하지 않는다.
 * 설정 화면의 상시 진입점은 이 플래그와 무관하게 항상 표시된다.
 */

const WIDGET_PROMO_SEEN_KEY = 'withgod.widgetPromo.seen';

export const hasSeenWidgetPromo = async (): Promise<boolean> => {
  return (await getStorageItem(WIDGET_PROMO_SEEN_KEY)) === 'true';
};

export const markWidgetPromoSeen = async (): Promise<void> => {
  await setStorageItem(WIDGET_PROMO_SEEN_KEY, 'true');
};
