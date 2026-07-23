/**
 * 앱 공통 색상 팔레트.
 *
 * 화면별 하드코딩 대신 이 토큰을 사용한다. 알파 변형(rgba)·그라데이션
 * 파생색은 사용처가 한 곳뿐이라 각 화면에 남겨둔다.
 */
export const colors = {
  /** 브랜드 블루 */
  primary: "#4A90E2",
  /** 화면 기본 배경 */
  background: "#F9FAFB",
  /** 제목 등 가장 진한 텍스트 */
  textPrimary: "#101828",
  /** 보조 텍스트 */
  textSecondary: "#6A7282",
  /** 구분선·테두리 */
  border: "#E5E7EB",
  /** 저장(하트) 활성 색 — 좋아요 버튼 관례에 맞춘 레드 */
  heartActive: "#ED4956",
  /** 비활성 아이콘 (하트 미저장, 복사/공유 기본) */
  iconMuted: "#9CA3AF",
} as const;
