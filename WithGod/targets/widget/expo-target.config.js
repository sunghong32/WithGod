/** @type {import('@bacons/apple-targets/app.plugin').Config} */
module.exports = {
  type: "widget",
  name: "DailyVerseWidget",
  displayName: "오늘의 말씀",
  // 접두사 점(.)은 본앱 번들 ID 뒤에 붙는다 → kr.co.mincha.withgod.widget
  bundleIdentifier: ".widget",
  // 템플릿 기본값(18.0)은 iOS 17 사용자를 배제하므로 명시적으로 낮춘다
  deploymentTarget: "17.0",
  frameworks: ["SwiftUI", "WidgetKit"],
  colors: {
    accent: "#4A90E2",
    widgetBackground: { color: "#FFFFFF", darkColor: "#1C1C1E" },
  },
};
