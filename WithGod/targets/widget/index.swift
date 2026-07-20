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

// MARK: - Timeline

struct VerseEntry: TimelineEntry {
  let date: Date
  let reference: String
  let text: String
}

private let placeholderEntry = VerseEntry(
  date: Date(),
  reference: "이사야 41:10",
  text: "두려워하지 말라 내가 너와 함께 함이라 놀라지 말라 나는 네 하나님이 됨이라."
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
    guard let url = URL(string: "https://mincha.co.kr/daily-verse") else {
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
        Text("오늘의 말씀")
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
    .configurationDisplayName("오늘의 말씀")
    .description("매일 새로운 말씀을 홈 화면에서 만나보세요.")
    .supportedFamilies([.systemMedium])
  }
}

@main
struct ExportedWidgets: WidgetBundle {
  var body: some Widget {
    DailyVerseWidget()
  }
}
