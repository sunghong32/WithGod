import SwiftUI
import WidgetKit

// MARK: - API 응답 모델 (GET https://mincha.co.kr/daily-verse)

private struct DailyVerseResponse: Codable {
  let daily_verse: DailyVerse
}

private struct DailyVerse: Codable {
  let reference: String
  let text: String
}

// MARK: - 캐시 (위젯 익스텐션 자체 UserDefaults — 앱과 공유할 필요 없음)

private enum VerseCache {
  private static let referenceKey = "withgod.widget.reference"
  private static let textKey = "withgod.widget.text"

  static func save(_ verse: DailyVerse) {
    let defaults = UserDefaults.standard
    defaults.set(verse.reference, forKey: referenceKey)
    defaults.set(verse.text, forKey: textKey)
  }

  static func load() -> DailyVerse? {
    let defaults = UserDefaults.standard
    guard
      let reference = defaults.string(forKey: referenceKey),
      let text = defaults.string(forKey: textKey)
    else { return nil }
    return DailyVerse(reference: reference, text: text)
  }
}

// MARK: - 현지화 (앱 로케일 widget.* 문구와 동일 — 이슈 #14 위젯 라벨 버그 수정)
// 위젯 확장은 앱 JS i18n 을 못 쓰므로 기기 선호 언어 기준으로 직접 고른다.
// 미지원 언어는 영어(국제 관례), 폴백 최종값은 한국어.

private enum L10n {
  static var lang: String {
    // 1순위: 앱에서 수동 선택한 언어(App Group 공유, WidgetBridge 가 기록).
    // 없으면(시스템 따르기) 기기 선호 언어를 쓴다.
    if let stored = UserDefaults(suiteName: "group.kr.co.mincha.withgod")?
      .string(forKey: "withgod.language"), supported.contains(stored) {
      return stored
    }
    let raw = Locale.preferredLanguages.first ?? "ko"
    let code = raw.split(separator: "-").first.map(String.init)?.lowercased() ?? "ko"
    return supported.contains(code) ? code : "en"
  }

  private static let supported: Set<String> = ["ko", "en", "es", "pt", "de", "fr", "it", "pl"]

  static var headerLabel: String {
    switch lang {
    case "en": return "Today's Verse"
    case "es": return "Versículo del día"
    case "pt": return "Versículo do dia"
    case "de": return "Vers des Tages"
    case "fr": return "Verset du jour"
    case "it": return "Versetto del giorno"
    case "pl": return "Werset dnia"
    default: return "오늘의 말씀"
    }
  }

  static var galleryDescription: String {
    switch lang {
    case "en": return "Meet a new Bible verse on your home screen every day."
    case "es": return "Un versículo bíblico nuevo cada día en tu pantalla de inicio."
    case "pt": return "Um novo versículo bíblico todos os dias na sua tela inicial."
    case "de": return "Jeden Tag ein neuer Bibelvers auf deinem Startbildschirm."
    case "fr": return "Chaque jour un nouveau verset biblique sur votre écran d'accueil."
    case "it": return "Ogni giorno un nuovo versetto biblico nella schermata iniziale."
    case "pl": return "Codziennie nowy werset biblijny na ekranie głównym."
    default: return "매일 새로운 말씀을 홈 화면에서 만나보세요."
    }
  }

  // 첫 로드 전·갤러리 미리보기용 자리표시 구절 (각 언어 성경의 이사야 41:10)
  static var placeholderVerse: (reference: String, text: String) {
    switch lang {
    case "en": return ("Isaiah 41:10", "Don’t you be afraid, for I am with you. Don’t be dismayed, for I am your God.")
    case "es": return ("Isaías 41:10", "No temas, que yo soy contigo; no desmayes, que yo soy tu Dios que te esfuerzo.")
    case "pt": return ("Isaías 41:10", "Não temas, porque eu estou contigo; não te assombres, porque eu sou teu Deus.")
    case "de": return ("Jesaja 41:10", "Fürchte dich nicht, ich bin mit dir; weiche nicht, denn ich bin dein Gott.")
    case "fr": return ("Ésaïe 41:10", "Ne crains rien, car je suis avec toi; car je suis ton Dieu.")
    case "it": return ("Isaia 41:10", "Tu, non temere, perché io son teco; non ti smarrire, perché io sono il tuo Dio.")
    case "pl": return ("Izajasza 41:10", "Nie bój się, bo ja jestem z tobą. Nie lękaj się, bo ja jestem twoim Bogiem.")
    default: return ("이사야 41:10", "두려워하지 말라 내가 너와 함께 함이라 놀라지 말라 나는 네 하나님이 됨이라.")
    }
  }
}

// MARK: - Timeline

struct VerseEntry: TimelineEntry {
  let date: Date
  let reference: String
  let text: String
}

private let placeholderEntry = VerseEntry(
  date: Date(),
  reference: L10n.placeholderVerse.reference,
  text: L10n.placeholderVerse.text
)

struct Provider: TimelineProvider {
  func placeholder(in context: Context) -> VerseEntry {
    placeholderEntry
  }

  func getSnapshot(in context: Context, completion: @escaping (VerseEntry) -> Void) {
    if let cached = VerseCache.load() {
      completion(VerseEntry(date: Date(), reference: cached.reference, text: cached.text))
    } else {
      completion(placeholderEntry)
    }
  }

  func getTimeline(in context: Context, completion: @escaping (Timeline<VerseEntry>) -> Void) {
    Task {
      do {
        let verse = try await fetchDailyVerse()
        VerseCache.save(verse)
        let entry = VerseEntry(date: Date(), reference: verse.reference, text: verse.text)
        // WidgetKit 갱신은 best-effort라 자정 정각이 아닌 자정 직후로 요청한다
        completion(Timeline(entries: [entry], policy: .after(nextKstMidnight())))
      } catch {
        // 네트워크 실패: 마지막 말씀 유지 + 30분 후 재시도
        let fallback = VerseCache.load()
        let entry = VerseEntry(
          date: Date(),
          reference: fallback?.reference ?? placeholderEntry.reference,
          text: fallback?.text ?? placeholderEntry.text
        )
        completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(30 * 60))))
      }
    }
  }

  private func fetchDailyVerse() async throws -> DailyVerse {
    // 위젯 언어(앱 내 선택 우선, 없으면 기기 언어 — L10n.lang)로 말씀을 요청한다.
    // 미지원 언어는 서버가 한국어로 폴백한다(이슈 #12·#14).
    var components = URLComponents(string: "https://mincha.co.kr/daily-verse")!
    components.queryItems = [URLQueryItem(name: "lang", value: L10n.lang)]
    guard let url = components.url else {
      throw URLError(.badURL)
    }
    var request = URLRequest(url: url)
    request.timeoutInterval = 15
    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode(DailyVerseResponse.self, from: data).daily_verse
  }

  /// 다음 KST 자정 + 5분. 서버의 오늘의 말씀이 KST 날짜 기준으로 바뀌므로
  /// 기기 시간대와 무관하게 Asia/Seoul 로 계산한다.
  private func nextKstMidnight() -> Date {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(identifier: "Asia/Seoul") ?? .current
    let startOfToday = calendar.startOfDay(for: Date())
    let nextMidnight =
      calendar.date(byAdding: .day, value: 1, to: startOfToday)
      ?? Date().addingTimeInterval(24 * 60 * 60)
    return nextMidnight.addingTimeInterval(5 * 60)
  }
}

// MARK: - View (systemMedium)

struct DailyVerseWidgetEntryView: View {
  var entry: Provider.Entry

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      HStack(spacing: 6) {
        RoundedRectangle(cornerRadius: 2)
          .fill(Color("accent"))
          .frame(width: 3, height: 13)
        Text(L10n.headerLabel)
          .font(.caption)
          .fontWeight(.semibold)
          .foregroundStyle(.secondary)
        Spacer()
      }

      Text(entry.text)
        .font(.subheadline)
        .foregroundStyle(.primary)
        .lineSpacing(2)
        .lineLimit(3)
        .minimumScaleFactor(0.85)
        .fixedSize(horizontal: false, vertical: true)

      Spacer(minLength: 0)

      HStack {
        Spacer()
        Text(entry.reference)
          .font(.caption)
          .fontWeight(.semibold)
          .foregroundStyle(Color("accent"))
      }
    }
    .containerBackground(for: .widget) {
      Color("widgetBackground")
    }
    .widgetURL(URL(string: "withgod://"))
  }
}

// MARK: - Widget

struct DailyVerseWidget: Widget {
  let kind: String = "DailyVerseWidget"

  var body: some WidgetConfiguration {
    StaticConfiguration(kind: kind, provider: Provider()) { entry in
      DailyVerseWidgetEntryView(entry: entry)
    }
    .configurationDisplayName(L10n.headerLabel)
    .description(L10n.galleryDescription)
    .supportedFamilies([.systemMedium])
  }
}

@main
struct ExportedWidgets: WidgetBundle {
  var body: some Widget {
    DailyVerseWidget()
  }
}
