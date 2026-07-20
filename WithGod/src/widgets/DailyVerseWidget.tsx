import { FlexWidget, TextWidget } from "react-native-android-widget";

export interface DailyVerseWidgetProps {
  reference: string;
  text: string;
  dark?: boolean;
}

/**
 * 안드로이드 홈 화면 '오늘의 말씀' 위젯 (4x2).
 * react-native-android-widget 프리미티브만 사용 가능하다(일반 RN 컴포넌트 불가).
 * 탭하면 앱이 열린다.
 */
export function DailyVerseWidget({
  reference,
  text,
  dark = false,
}: DailyVerseWidgetProps) {
  const background = dark ? "#1C1C1E" : "#FFFFFF";
  const bodyColor = dark ? "#ECEDEE" : "#1E2939";
  const labelColor = dark ? "#9BA1A6" : "#6A7282";

  return (
    <FlexWidget
      clickAction="OPEN_APP"
      style={{
        height: "match_parent",
        width: "match_parent",
        backgroundColor: background,
        borderRadius: 16,
        padding: 16,
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      <FlexWidget
        style={{
          flexDirection: "row",
          alignItems: "center",
          width: "match_parent",
        }}
      >
        <FlexWidget
          style={{
            width: 3,
            height: 13,
            backgroundColor: "#4A90E2",
            borderRadius: 2,
            marginRight: 6,
          }}
        />
        <TextWidget
          text="오늘의 말씀"
          style={{ fontSize: 12, color: labelColor }}
        />
      </FlexWidget>

      <TextWidget
        text={text}
        maxLines={3}
        truncate="END"
        style={{
          fontSize: 14,
          color: bodyColor,
          width: "match_parent",
          marginTop: 8,
          marginBottom: 8,
        }}
      />

      <TextWidget
        text={reference}
        style={{
          fontSize: 12,
          color: "#4A90E2",
          width: "match_parent",
          textAlign: "right",
        }}
      />
    </FlexWidget>
  );
}
