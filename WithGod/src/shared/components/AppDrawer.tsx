import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Animated,
  BackHandler,
  Dimensions,
  Easing,
  PanResponder,
  Platform,
  StyleSheet,
  ToastAndroid,
  View,
} from "react-native";
import { t } from "@/shared/lib/i18n";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { setLeftEdgeGestureExclusion } from "../../../modules/gesture-exclusion";

/**
 * 기록 사이드바 드로어.
 *
 * **플랫폼마다 여는 방식이 다르다.** ChatGPT·Claude 앱도 그렇게 한다.
 * - iOS: 메인 화면이 오른쪽으로 **밀리며** 아래 깔린 사이드바가 드러난다.
 *        밀린 화면은 모서리가 둥글어져 카드처럼 보인다.
 * - Android: 메인 화면은 그대로 있고 사이드바가 **위로 덮으며** 들어온다.
 *        나머지 영역은 스크림(어두운 막)으로 덮인다. 머티리얼의 모달 드로어 규칙.
 *
 * 두 방식이 공유하는 것(제스처·열림 상태·탭 닫기)은 그대로 두고 표현만 갈랐다.
 *
 * 구현 메모:
 * - 신규 네이티브 의존성을 두지 않는 방침에 따라 RN 내장 Animated + PanResponder 사용
 * - 사이드바는 **항상 마운트**한다. 스와이프로 살짝 드러나는 순간에도 내용이
 *   이미 차 있어야 하기 때문이다(열린 뒤에 조회하면 빈 화면이 스친다).
 */

const SCREEN_WIDTH = Dimensions.get("window").width;
export const DRAWER_WIDTH = Math.min(320, Math.round(SCREEN_WIDTH * 0.82));

const IS_ANDROID = Platform.OS === "android";
const OPEN_MS = 280;
// 닫힘은 조금 더 짧게 — 사용자는 이미 "닫겠다"고 결정한 상태라 기다림이 거슬린다.
const CLOSE_MS = 210;
/**
 * 좌측 엣지 — **손이 닿는 즉시** 드로어가 선점하는 구간.
 *
 * 드로어는 화면 어디서 밀어도 열리지만(아래 OPEN_ANYWHERE_*), 엣지만은 움직임을
 * 기다리지 않고 터치 다운에 바로 가져간다. 스크롤 뷰의 네이티브 인식기와 경쟁하는
 * 구간이라 한 프레임만 늦어도 뺏기기 때문이다.
 *
 * 안드로이드는 제스처 내비게이션에서 화면 맨 왼쪽 약 20dp 를 시스템 뒤로가기가
 * 가져가는데, [[gesture-exclusion]] 네이티브 모듈로 그 구간을 넘겨받아
 * 맨 끝에서 밀어도 열리게 한다(AndroidX DrawerLayout 과 같은 방식).
 * 넘겨받는 폭과 감지 폭을 같은 값으로 맞춘다.
 */
const EDGE_HIT_WIDTH = IS_ANDROID ? 40 : 24;
/**
 * 엣지 밖에서 시작한 스와이프를 드로어로 인정하는 기준 (ChatGPT·Claude 앱처럼
 * 화면 아무 데서나 밀어도 열리게 하는 부분).
 *
 * 엣지보다 **엄격하게** 잡는다. 세로 스크롤 중의 손떨림이나 버튼 위 미세한
 * 드래그까지 가져가면 화면이 제멋대로 밀리기 때문이다. 가로 이동이 세로의
 * 2배를 넘고, 12dp 이상 움직였을 때만 드로어가 받는다.
 */
const OPEN_ANYWHERE_DX = 12;
const OPEN_ANYWHERE_RATIO = 2;
/**
 * 화면 상단 이 높이(안전영역 제외)까지는 엣지 스와이프로 선점하지 않는다.
 *
 * 헤더 좌측의 메뉴(☰) 버튼이 엣지 폭 안에 들어와 있어서, 여기까지 터치 다운에
 * 선점해 버리면 **버튼이 눌리지 않는다**(실측). 헤더에서 가로로 끄는 동작은
 * 움직임 기반 판정이 대신 받아주므로 손해가 없다.
 */
const EDGE_TOP_EXCLUDE = 72;
/** 손을 뗐을 때 열림/닫힘을 가르는 지점 */
const SNAP_RATIO = 0.4;
/**
 * 열려 있을 때 덮인 화면을 "눌렀다"고 볼 가로 이동 한계(dp).
 *
 * **세로로 얼마나 흔들렸는지는 보지 않는다.** 손가락 탭은 세로로 쉽게 몇 dp 씩
 * 흔들리는데, 예전처럼 세로까지 6dp 안쪽을 요구하면 그 탭이 '드래그'로 분류되고
 * 스냅 계산이 도로 열림을 골라 **탭해도 안 닫힌다**(사용자 지적, 에뮬레이터에서
 * 세로 8dp 흔들림으로 재현). 덮인 화면 위 제스처는 어차피 '닫기' 말고 할 일이 없다.
 */
const DISMISS_TAP_DX = 16;
/** 홈에서 뒤로가기를 두 번 눌러야 앱이 꺼지게 하는 간격(ms) */
const EXIT_CONFIRM_MS = 2000;
/**
 * iOS: 밀려난 메인 화면의 모서리 둥글기.
 *
 * **기기 화면 자체의 둥근 모서리와 같은 크기**로 맞춘다. 그래야 화면이 통째로
 * 옆으로 밀려나는 느낌이 난다(ChatGPT·Claude 앱과 같은 인상). 끌린 정도에 따라
 * 서서히 둥글어지게 하면 안 된다 — 그 앱들도 처음부터 둥근 채로 밀린다.
 *
 * 노치·다이내믹 아일랜드가 있는 기기만 화면 모서리가 둥글다. 홈버튼 기기는 각지므로
 * 상단 안전영역 크기로 판별한다.
 */
const DEVICE_CORNER_RADIUS = 52;
const SCRIM_MAX_OPACITY = 0.4;

type DrawerContextValue = {
  open: () => void;
  close: () => void;
  isOpen: boolean;
  /** 조금이라도 드러나 있으면 true — 사이드바가 데이터를 새로 읽는 신호 */
  isVisible: boolean;
};

const DrawerContext = createContext<DrawerContextValue>({
  open: () => {},
  close: () => {},
  isOpen: false,
  isVisible: false,
});

export const useAppDrawer = () => useContext(DrawerContext);

type AppDrawerProps = {
  /** 메인 화면 */
  children: React.ReactNode;
  /** 사이드바 내용 */
  renderSidebar: () => React.ReactNode;
  /** 스와이프로 열 수 있는지 (홈이 아닌 화면에서는 끈다) */
  swipeEnabled?: boolean;
};

export function AppDrawer({
  children,
  renderSidebar,
  swipeEnabled = true,
}: AppDrawerProps) {
  // 0(닫힘) ~ DRAWER_WIDTH(열림). 제스처 계산을 픽셀로 하려고 이 단위를 쓴다.
  const translateX = useRef(new Animated.Value(0)).current;
  const insets = useSafeAreaInsets();
  // 홈버튼 기기(상단 안전영역이 작음)는 화면 모서리가 각지므로 깎지 않는다.
  const cornerRadius = insets.top > 24 ? DEVICE_CORNER_RADIUS : 0;

  const [isOpen, setIsOpen] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const isOpenRef = useRef(false);
  const isVisibleRef = useRef(false);
  // 뒤로가기 핸들러에서 읽어야 해서 ref 로도 들고 있는다(핸들러는 한 번만 등록된다)
  const isHomeRef = useRef(swipeEnabled);
  isHomeRef.current = swipeEnabled;
  // 헤더(메뉴 버튼이 있는 영역)의 아래 경계. 제스처 핸들러에서 읽어야 해서 ref.
  const edgeTopRef = useRef(0);
  edgeTopRef.current = insets.top + EDGE_TOP_EXCLUDE;

  // 홈에서 뒤로가기를 마지막으로 눌러 종료 안내를 띄운 시각
  const exitPromptAtRef = useRef(0);

  const markVisible = useCallback((visible: boolean) => {
    if (isVisibleRef.current === visible) return;
    isVisibleRef.current = visible;
    setIsVisible(visible);
  }, []);

  const animateTo = useCallback(
    (toValue: number, opening: boolean) => {
      if (opening) {
        isOpenRef.current = true;
        setIsOpen(true);
        markVisible(true);
      }
      Animated.timing(translateX, {
        toValue,
        duration: opening ? OPEN_MS : CLOSE_MS,
        // 열 때도 닫을 때도 **처음에 빠르고 끝에서 감속**한다.
        // 닫힘에 Easing.in 을 쓰면 손을 뗀 직후 거의 안 움직여 "멈칫"하는
        // 느낌을 준다(사용자 지적). 제스처의 기세를 이어받으려면 out 이어야 한다.
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start(({ finished }) => {
        if (!finished) return;
        isOpenRef.current = opening;
        setIsOpen(opening);
        if (!opening) markVisible(false);
      });
    },
    [markVisible, translateX],
  );

  const open = useCallback(() => animateTo(DRAWER_WIDTH, true), [animateTo]);
  const close = useCallback(() => animateTo(0, false), [animateTo]);

  // 안드로이드: 좌측 엣지를 시스템 뒤로가기 제스처에서 넘겨받는다.
  // 드로어가 닫혀 있고 스와이프가 켜져 있을 때만 가져오고, 그 외에는 반납해
  // 시스템 뒤로가기가 정상 동작하게 둔다.
  useEffect(() => {
    setLeftEdgeGestureExclusion(EDGE_HIT_WIDTH, swipeEnabled && !isOpen);
  }, [swipeEnabled, isOpen]);

  // 안드로이드 뒤로가기 처리. 뒤로가기 경로가 한 곳에 모여 있어야 순서가 꼬이지 않아
  // 여기서 전부 처리한다.
  //
  // 1) 드로어가 열려 있으면 닫는다.
  // 2) 홈(스택 최하단)이면 **앱을 내린다.** 이걸 기본 동작에 맡기면 expo-router 가
  //    마지막 화면까지 팝해 스택이 비고 **빈 흰 화면**이 남는다(실측). 좌측 엣지
  //    스와이프가 시스템 뒤로가기로 넘어갈 때마다 이 상태가 되어 사용자가
  //    "사이드바가 안 열리고 빈 화면이 뜬다"고 겪게 된다.
  // 3) 그 외(밀려 올라온 화면)는 기본 동작에 맡긴다.
  useEffect(() => {
    if (!IS_ANDROID) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (isOpenRef.current) {
        close();
        return true;
      }
      // swipeEnabled 는 "밀려 올라온 화면이 아니다" == 홈이라는 뜻이다.
      // router.canGoBack() 으로 판단하면 안 된다 — 홈인데도 참을 돌려주는 경우가
      // 있고, 그때 기본 동작에 맡기면 홈까지 팝돼 빈 화면이 남는다.
      if (isHomeRef.current) {
        // **한 번에 끄지 않는다.** 좌측 엣지 스와이프는 화면 하단 200dp 밖에서는
        // OS 가 시스템 뒤로가기로 가져가는데(제외 영역 상한), 그러면 사이드바를
        // 열려던 손짓이 그대로 앱 종료가 된다. 두 번 눌러야 꺼지게 해 사고를 막는다.
        const now = Date.now();
        if (now - exitPromptAtRef.current < EXIT_CONFIRM_MS) {
          BackHandler.exitApp();
          return true;
        }
        exitPromptAtRef.current = now;
        ToastAndroid.show(t("common.exitConfirm"), ToastAndroid.SHORT);
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [close]);

  const grantRef = useRef({ dx: 0, dy: 0 });
  const offsetFromGrant = useCallback(
    (gesture: { dx: number; dy: number }) => ({
      dx: gesture.dx - grantRef.current.dx,
      dy: gesture.dy - grantRef.current.dy,
    }),
    [],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        // 열려 있을 때 덮인/밀린 화면을 건드리면 **capture 단계에서** 가로챈다.
        // 콘텐츠 위에 Pressable 을 얹는 방식은 네이티브 스택이 터치를 먼저
        // 가져가는 경우가 있어 신뢰할 수 없다.
        onStartShouldSetPanResponderCapture: (evt) => {
          // 열려 있을 때: 덮인/밀린 화면을 건드리면 가로챈다(탭으로 닫기).
          if (isOpenRef.current) return evt.nativeEvent.pageX > DRAWER_WIDTH;
          // 닫혀 있을 때: 좌측 엣지에서 시작한 터치는 **손이 닿는 즉시** 선점한다.
          //
          // 움직임을 보고 판단하면 늦다. 실제 손가락은 처음 몇 샘플이 dx 1~2px
          // 수준이라 그 사이 ScrollView 의 네이티브 제스처 인식기가 터치를
          // 가져가고, 한번 넘어가면 되찾을 수 없다(iOS 에서 특히 심하다).
          // 엣지 폭이 좁아(24~40dp) 그 안의 탭·세로 스크롤을 포기해도 손해가 적다.
          //
          // 단, **헤더는 제외한다.** 좌측 메뉴(☰) 버튼이 엣지 폭 안에 있어서
          // 여기까지 선점하면 버튼이 눌리지 않는다.
          return (
            isHomeRef.current &&
            evt.nativeEvent.pageX <= EDGE_HIT_WIDTH &&
            evt.nativeEvent.pageY > edgeTopRef.current
          );
        },
        onMoveShouldSetPanResponderCapture: (evt, gesture) => {
          const absDx = Math.abs(gesture.dx);
          const absDy = Math.abs(gesture.dy);
          // 열려 있으면 화면 어디서든 왼쪽 스와이프로 닫는다(홈이 아니어도).
          if (isOpenRef.current) {
            return gesture.dx < 0 && absDx > absDy * 1.2 && absDx > 3;
          }
          if (!swipeEnabled) return false;
          // **스와이프가 시작된 지점**으로 판단한다. evt 의 pageX 는 지금 손가락
          // 위치라 이동한 만큼(dx) 빼야 시작점이 나온다 — 그냥 pageX 를 쓰면
          // 엣지에서 시작한 스와이프도 몇 px 만 움직이면 엣지 밖으로 읽힌다.
          const startX = evt.nativeEvent.pageX - gesture.dx;
          const fromEdge = startX <= EDGE_HIT_WIDTH;
          // 엣지는 임계값을 낮게 잡아 **최대한 일찍** 선점한다. 늦게 잡으면 첫 엣지
          // 스와이프를 네이티브 엣지 제스처 인식기가 먼저 가져가 버린다
          // (콜드 스타트 후 첫 스와이프만 실패하던 증상).
          // 엣지 밖은 세로 스크롤을 뺏지 않도록 더 엄격하게 본다.
          const minDx = fromEdge ? 3 : OPEN_ANYWHERE_DX;
          const minRatio = fromEdge ? 1.2 : OPEN_ANYWHERE_RATIO;
          return gesture.dx > minDx && absDx > absDy * minRatio;
        },
        // 드로어가 제스처를 넘겨받은 순간의 이동량. 화면 중간에서 시작한
        // 스와이프는 12dp 쯤 움직인 뒤에야 넘어오는데, 그 값을 그대로 쓰면
        // 사이드바가 그만큼 **툭 튀어나온다**. 넘겨받은 시점을 0 으로 잡는다.
        onPanResponderGrant: (_evt, gesture) => {
          grantRef.current = { dx: gesture.dx, dy: gesture.dy };
        },
        onPanResponderMove: (_evt, gesture) => {
          const { dx, dy } = offsetFromGrant(gesture);
          const base = isOpenRef.current ? DRAWER_WIDTH : 0;
          // 엣지에서 손을 댔지만 세로로 끄는 중이면 드로어를 움직이지 않는다.
          // (터치 다운에 선점하므로 세로 제스처도 우리에게 들어온다)
          if (base === 0 && Math.abs(dy) > Math.abs(dx) * 1.2) {
            return;
          }
          const next = Math.min(DRAWER_WIDTH, Math.max(0, base + dx));
          translateX.setValue(next);
          // 손가락으로 살짝 끌어낸 순간부터 사이드바를 '보이는' 상태로 친다.
          // 모서리도 이때 곧바로 완전히 둥글어진다(서서히 둥글어지지 않는다).
          if (next > 0) markVisible(true);
        },
        onPanResponderRelease: (_evt, gesture) => {
          const { dx } = offsetFromGrant(gesture);
          // 열려 있는데 가로로 거의 안 움직였으면 덮인 화면을 '누른' 것이다 → 닫는다.
          // 세로 흔들림은 따지지 않는다(위 DISMISS_TAP_DX 설명).
          if (isOpenRef.current && Math.abs(dx) < DISMISS_TAP_DX) {
            close();
            return;
          }
          const base = isOpenRef.current ? DRAWER_WIDTH : 0;
          const current = Math.min(DRAWER_WIDTH, Math.max(0, base + dx));
          // 빠르게 튕기면 위치와 무관하게 그 방향으로
          if (gesture.vx > 0.5) return open();
          if (gesture.vx < -0.5) return close();
          if (current > DRAWER_WIDTH * SNAP_RATIO) open();
          else close();
        },
        onPanResponderTerminationRequest: () => false,
      }),
    [close, markVisible, offsetFromGrant, open, swipeEnabled, translateX],
  );

  const value = useMemo(
    () => ({ open, close, isOpen, isVisible }),
    [open, close, isOpen, isVisible],
  );

  // 사이드바는 항상 마운트해 둔다 — 스와이프로 드러나는 즉시 내용이 보여야 한다.
  // **반드시 Animated.View 여야 한다.** 일반 View 에 Animated 값을 transform 으로
  // 넘기면 안드로이드 네이티브가 숫자로 읽으려다 앱이 죽는다(실측).
  const sidebar = (
    <Animated.View
      style={[
        styles.sidebar,
        IS_ANDROID
          ? {
              transform: [
                {
                  translateX: translateX.interpolate({
                    inputRange: [0, DRAWER_WIDTH],
                    outputRange: [-DRAWER_WIDTH, 0],
                  }),
                },
              ],
            }
          : null,
      ]}
      pointerEvents={isOpen ? "auto" : "none"}
    >
      {renderSidebar()}
    </Animated.View>
  );

  // 이동은 바깥 뷰(네이티브 드라이버), 모서리는 안쪽 뷰가 맡는다.
  // 한 뷰에 네이티브·JS 드라이버를 섞으면 신아키텍처에서 Hermes 세그폴트가 난다(실측).
  // 모서리는 애니메이션하지 않고 드러나는 즉시 완전한 값으로 적용한다.
  const content = IS_ANDROID ? (
    <View style={styles.content}>{children}</View>
  ) : (
    <Animated.View style={[styles.content, { transform: [{ translateX }] }]}>
      <View
        style={[
          styles.contentSurface,
          { borderRadius: isVisible ? cornerRadius : 0 },
        ]}
      >
        {children}
      </View>
    </Animated.View>
  );

  return (
    <DrawerContext.Provider value={value}>
      <View style={styles.root} {...panResponder.panHandlers}>
        {IS_ANDROID ? (
          <>
            {/* 안드로이드: 메인 화면은 제자리, 사이드바가 위로 덮는다 */}
            {content}
            <Animated.View
              pointerEvents="none"
              style={[
                styles.scrim,
                {
                  opacity: translateX.interpolate({
                    inputRange: [0, DRAWER_WIDTH],
                    outputRange: [0, SCRIM_MAX_OPACITY],
                  }),
                },
              ]}
            />
            {sidebar}
          </>
        ) : (
          <>
            {/* iOS: 사이드바가 아래에 깔리고 메인 화면이 밀리며 드러난다 */}
            {sidebar}
            {content}
          </>
        )}
      </View>
    </DrawerContext.Provider>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F7F8FA",
  },
  sidebar: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: DRAWER_WIDTH,
    backgroundColor: "#F7F8FA",
    ...(IS_ANDROID
      ? {
          // 덮는 방식이라 사이드바가 그림자를 갖는다
          elevation: 16,
        }
      : null),
  },
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#111827",
  },
  content: {
    flex: 1,
    ...(IS_ANDROID
      ? { backgroundColor: "#FFFFFF" }
      : {
          // 밀려난 화면이 사이드바보다 위에 있음을 그림자로 보인다.
          // 그림자를 주는 뷰는 overflow 를 잘라선 안 되므로 표면 뷰와 분리한다.
          shadowColor: "#000000",
          shadowOffset: { width: -3, height: 0 },
          shadowOpacity: 0.14,
          shadowRadius: 10,
        }),
  },
  // 실제 화면 내용을 담는 면 — 여기만 모서리를 깎는다
  contentSurface: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    overflow: "hidden",
  },
});
