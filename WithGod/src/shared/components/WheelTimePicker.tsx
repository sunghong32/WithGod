import { baseFontFamily } from "@/shared/styles";
import { useEffect, useRef } from "react";
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

const ITEM_HEIGHT = 40;
const VISIBLE_ROWS = 3;
const PAD_ROWS = (VISIBLE_ROWS - 1) / 2;
const WRAP_HEIGHT = ITEM_HEIGHT * VISIBLE_ROWS;

const PERIODS = ["오전", "오후"];
const HOURS = Array.from({ length: 12 }, (_, i) => String(i + 1));
const MINUTES = Array.from({ length: 60 }, (_, i) =>
  String(i).padStart(2, "0"),
);

type ColumnProps = {
  items: string[];
  index: number;
  onChange: (index: number) => void;
  width: number;
  disabled?: boolean;
};

function WheelColumn({ items, index, onChange, width, disabled }: ColumnProps) {
  const ref = useRef<ScrollView>(null);
  const internal = useRef(index);
  const didInit = useRef(false);

  const scrollToIndex = (i: number, animated: boolean) =>
    ref.current?.scrollTo({ y: i * ITEM_HEIGHT, animated });

  const onLayout = () => {
    if (didInit.current) return;
    didInit.current = true;
    internal.current = index;
    scrollToIndex(index, false);
  };

  // 외부에서 값이 바뀌면(설정 로드 등) 스크롤 위치 동기화. 사용자 스크롤과 충돌 방지 위해 가드.
  useEffect(() => {
    if (!didInit.current) return;
    if (index !== internal.current) {
      internal.current = index;
      scrollToIndex(index, false);
    }
  }, [index]);

  const settle = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = e.nativeEvent.contentOffset.y;
    let i = Math.round(y / ITEM_HEIGHT);
    i = Math.max(0, Math.min(items.length - 1, i));
    internal.current = i;
    scrollToIndex(i, true);
    if (i !== index) onChange(i);
  };

  return (
    <ScrollView
      ref={ref}
      onLayout={onLayout}
      style={{ width, height: WRAP_HEIGHT }}
      showsVerticalScrollIndicator={false}
      snapToInterval={ITEM_HEIGHT}
      decelerationRate="fast"
      scrollEnabled={!disabled}
      nestedScrollEnabled
      onMomentumScrollEnd={settle}
      onScrollEndDrag={settle}
      contentContainerStyle={{ paddingVertical: ITEM_HEIGHT * PAD_ROWS }}
    >
      {items.map((it, i) => (
        <View key={i} style={styles.item}>
          <Text
            style={[
              styles.itemText,
              i === index && styles.itemTextActive,
              disabled && styles.itemTextDisabled,
            ]}
          >
            {it}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

type Props = {
  hour: number;
  minute: number;
  onChange: (hour: number, minute: number) => void;
  disabled?: boolean;
};

/**
 * 인라인 휠 시간 선택기 (오전/오후 · 시 · 분).
 * 네이티브 모듈 없이 ScrollView snap 으로 구현 — 위아래로 굴려서 시간 설정.
 */
export function WheelTimePicker({ hour, minute, onChange, disabled }: Props) {
  const periodIndex = hour < 12 ? 0 : 1;
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  const hourIndex = hour12 - 1;
  const minuteIndex = Math.max(0, Math.min(59, minute));

  const emit = (pIdx: number, hIdx: number, mIdx: number) => {
    const h12 = hIdx + 1;
    const base = h12 % 12; // 12시 -> 0
    const h24 = pIdx === 0 ? base : base + 12; // 오전/오후
    onChange(h24, mIdx);
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.band} pointerEvents="none" />
      <View style={styles.row}>
        <WheelColumn
          items={PERIODS}
          index={periodIndex}
          width={62}
          disabled={disabled}
          onChange={(i) => emit(i, hourIndex, minuteIndex)}
        />
        <WheelColumn
          items={HOURS}
          index={hourIndex}
          width={52}
          disabled={disabled}
          onChange={(i) => emit(periodIndex, i, minuteIndex)}
        />
        <Text style={styles.colon}>:</Text>
        <WheelColumn
          items={MINUTES}
          index={minuteIndex}
          width={52}
          disabled={disabled}
          onChange={(i) => emit(periodIndex, hourIndex, i)}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: WRAP_HEIGHT,
    position: "relative",
  },
  band: {
    position: "absolute",
    top: ITEM_HEIGHT * PAD_ROWS,
    left: 6,
    right: 6,
    height: ITEM_HEIGHT,
    backgroundColor: "#F0F6FE",
    borderRadius: 10,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: "#DCE8F8",
  },
  row: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    height: WRAP_HEIGHT,
  },
  item: {
    height: ITEM_HEIGHT,
    justifyContent: "center",
    alignItems: "center",
  },
  itemText: {
    fontSize: 20,
    color: "#C5CBD3",
    fontFamily: baseFontFamily,
  },
  itemTextActive: {
    color: "#1E2939",
    fontWeight: "500",
  },
  itemTextDisabled: {
    color: "#E1E3E7",
  },
  colon: {
    fontSize: 20,
    color: "#9AA1AC",
    marginHorizontal: 2,
    fontFamily: baseFontFamily,
  },
});
