import ExpoModulesCore
import WidgetKit

/// 앱 내 언어 선택을 위젯 익스텐션과 공유한다 (이슈 #14 후속).
/// 위젯은 별도 프로세스라 JS 저장소를 못 읽으므로 App Group UserDefaults 를 쓴다.
public class WidgetBridgeModule: Module {
  private static let appGroupId = "group.kr.co.mincha.withgod"
  private static let languageKey = "withgod.language"

  public func definition() -> ModuleDefinition {
    Name("WidgetBridge")

    // lang: 언어 코드("en" 등) 또는 nil(시스템 따르기 — 공유값 제거)
    Function("setSharedLanguage") { (lang: String?) in
      let defaults = UserDefaults(suiteName: Self.appGroupId)
      if let lang, !lang.isEmpty {
        defaults?.set(lang, forKey: Self.languageKey)
      } else {
        defaults?.removeObject(forKey: Self.languageKey)
      }
    }

    Function("reloadWidgets") {
      WidgetCenter.shared.reloadAllTimelines()
    }
  }
}
