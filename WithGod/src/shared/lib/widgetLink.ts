/**
 * 위젯 딥링크(실행 중 재진입) 처리를 루트 레이아웃에 위임하는 브리지.
 *
 * +native-intent 는 React 밖에서 실행돼 내비게이션 옵션(애니메이션)을 만질 수
 * 없다. 루트 레이아웃이 핸들러를 등록해 두면, 딥링크 순간 화면 전환 애니메이션을
 * 끄고 즉시 홈 탭으로 팝한다(이슈 #16 — 위젯 탭 시 '증발' 전환 제거).
 */
type Handler = () => void;

let handler: Handler | null = null;

export const setWidgetHomeHandler = (next: Handler | null): void => {
  handler = next;
};

/** 등록된 핸들러를 실행하고, 처리 여부를 반환한다. */
export const emitWidgetHome = (): boolean => {
  if (!handler) {
    return false;
  }
  handler();
  return true;
};
