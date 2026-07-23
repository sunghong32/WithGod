/**
 * 텔레메트리용 ID 생성.
 *
 * crypto/uuid 폴리필(react-native-get-random-values)이 없고 신규 네이티브
 * 의존성 추가가 금지돼 있어, notificationSettings 의 device_id 와 같은 방식으로
 * timestamp + 다중 Math.random 을 조합한다. 충돌하면 서버가 중복으로 보고
 * 버릴 뿐이라(event_id 가 PK) 암호학적 강도는 필요 없다.
 */

const chunk = (): string => Math.random().toString(36).slice(2, 10);

export const createEventId = (): string =>
  `ev-${Date.now().toString(36)}-${chunk()}${chunk()}`;

export const createSessionId = (): string =>
  `se-${Date.now().toString(36)}-${chunk()}`;
