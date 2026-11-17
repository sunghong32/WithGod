import { useCallback, useEffect, useSyncExternalStore } from "react";
import { Platform } from "react-native";

/**
 * 앱이 스스로 띄우는 안내 모달(통계 동의·업데이트·알림 프라이밍·AI 사과·위젯 안내)을
 * **한 번에 하나만** 보이게 하는 차례표.
 *
 * iOS 는 모달 하나가 떠 있는 동안(닫히는 애니메이션 중 포함) 다른 모달을 present 하지
 * 못한다. RN Modal 은 거절돼도 다시 시도하지 않고, 화면 크기의 호스트 뷰가 보이지 않는 채
 * 남아 터치를 전부 가져간다 — 그 화면이 통째로 먹통이 된다(#92). 예: 업데이트 안내가 떠
 * 있을 때 홈의 알림 프라이밍이 뜨려 하면, 「나중에」를 눌러도 홈이 터치를 받지 않는다.
 *
 * 그래서 띄우고 싶은 모달은 차례를 요청하고, 앞 모달이 **완전히 닫힌 뒤**(onDismiss)에
 * 뜬다. 요청한 순서대로 띄운다. 안드로이드는 Dialog 라 겹쳐도 되지만 순서는 같게 한다.
 */

type Listener = () => void;

/** onDismiss 가 오지 않을 때 차례를 넘기기까지 기다리는 시간. 닫힘 애니메이션(약 0.3초)보다 넉넉히. */
const RELEASE_FALLBACK_MS = 800;

/** 차례를 쥔 모달. 닫히는 중에도 닫힘이 끝날 때까지 쥐고 있다. */
let current: string | null = null;
/** 차례를 쥔 모달이 닫히는 중인지(더는 띄울 필요가 없음). */
let closing = false;
let fallbackTimer: ReturnType<typeof setTimeout> | null = null;
const waiting: string[] = [];
const listeners = new Set<Listener>();

const subscribe = (listener: Listener) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

const getCurrent = () => current;

const clearFallback = () => {
  if (fallbackTimer !== null) {
    clearTimeout(fallbackTimer);
    fallbackTimer = null;
  }
};

const advance = () => {
  if (current === null && waiting.length > 0) {
    current = waiting.shift() ?? null;
    closing = false;
  }
  listeners.forEach((listener) => listener());
};

const release = (id: string) => {
  if (current !== id) return;
  clearFallback();
  current = null;
  closing = false;
  advance();
};

const request = (id: string) => {
  if (current === id) {
    // 닫히는 도중에 다시 띄우려는 경우 — 차례를 그대로 이어서 쥔다
    closing = false;
    clearFallback();
    return;
  }
  if (!waiting.includes(id)) waiting.push(id);
  advance();
};

const withdraw = (id: string) => {
  const index = waiting.indexOf(id);
  if (index >= 0) {
    waiting.splice(index, 1);
    return;
  }
  if (current !== id) return;
  if (Platform.OS !== "ios") {
    release(id);
    return;
  }
  // iOS 는 닫힘 애니메이션이 끝나야(onDismiss) 다음 모달을 present 할 수 있다.
  // 한 번도 present 되지 못했거나 언마운트되면 onDismiss 가 오지 않으니 시간으로도 넘긴다.
  closing = true;
  clearFallback();
  fallbackTimer = setTimeout(() => release(id), RELEASE_FALLBACK_MS);
};

const dismissed = (id: string) => {
  if (current === id && closing) release(id);
};

/**
 * 모달을 띄우고 싶은지(`wanted`)를 알리고, 지금 실제로 보여도 되는지 받는다.
 * 돌려받은 `visible`·`onDismiss` 를 그대로 `<Modal>` 에 넘길 것 — onDismiss 가 있어야
 * 닫힘이 끝나자마자 다음 모달로 차례가 넘어간다.
 *
 * @param id 모달마다 고유한 이름
 */
export function useModalTurn(id: string, wanted: boolean) {
  const holder = useSyncExternalStore(subscribe, getCurrent, getCurrent);

  useEffect(() => {
    if (!wanted) return;
    request(id);
    return () => withdraw(id);
  }, [id, wanted]);

  const onDismiss = useCallback(() => dismissed(id), [id]);

  return { visible: wanted && holder === id, onDismiss };
}
