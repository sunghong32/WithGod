import { useSyncExternalStore } from "react";
import { Platform } from "react-native";

/**
 * iPadOS 26 창 조절 버튼(●●●)이 차지하는 폭 — 화면 맨 위에 한 줄로 놓인 바(헤더)가
 * 평소 안전영역보다 더 들어가야 하는 만큼(dp). 창 모드 iPad 에서 왼쪽 56.5 안팎이다.
 *
 * 창 버튼은 safeAreaInsets 에 잡히지 않아 react-native-safe-area-context 로는 못 피한다.
 * 아이폰·Android·iOS 26 미만·네이티브 모듈이 없는 구 빌드(OTA 로 이 JS 만 받은 경우)는
 * 모두 0 이라 지금과 똑같이 그린다. [[widget-bridge]] 와 같은 방식.
 */
export interface WindowControlsInsets {
  left: number;
  right: number;
}

const ZERO: WindowControlsInsets = { left: 0, right: 0 };

interface WindowControlsNative {
  getInsets(): WindowControlsInsets;
  addListener(
    eventName: "onChange",
    listener: (insets: WindowControlsInsets) => void,
  ): { remove(): void };
}

const loadNative = (): WindowControlsNative | null => {
  if (Platform.OS !== "ios") return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 모듈 미탑재 환경 폴백
    const { requireNativeModule } = require("expo-modules-core");
    return requireNativeModule("WindowControls");
  } catch {
    // 미탑재 — 다음 네이티브 빌드부터 동작
    return null;
  }
};

const native = loadNative();

const sameInsets = (a: WindowControlsInsets, b: WindowControlsInsets) =>
  a.left === b.left && a.right === b.right;

let current: WindowControlsInsets = ZERO;
if (native) {
  try {
    const initial = native.getInsets();
    if (!sameInsets(initial, ZERO)) current = initial;
  } catch {
    // 초기값을 못 읽어도 onChange 로 곧 들어온다
  }
}

const listeners = new Set<() => void>();

// 앱 전체에서 리스너 하나만 둔다(헤더가 늘 떠 있어 끊을 일이 없다).
native?.addListener("onChange", (next) => {
  if (sameInsets(next, current)) return;
  current = sameInsets(next, ZERO) ? ZERO : next;
  listeners.forEach((notify) => notify());
});

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

const getSnapshot = () => current;

/** 창 버튼 영역. 창 모드에 들어가거나 창 크기가 바뀌면 다시 그린다. */
export const useWindowControlsInsets = (): WindowControlsInsets =>
  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
