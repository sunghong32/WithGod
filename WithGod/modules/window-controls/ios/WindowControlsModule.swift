import ExpoModulesCore
import UIKit

/// iPadOS 26 창 모드의 창 조절 버튼(●●●)이 차지하는 폭을 JS 로 넘긴다 (이슈 #26).
///
/// 창 버튼은 창의 왼쪽 위 모서리에 떠 있는데 safeAreaInsets 에는 잡히지 않는다
/// (react-native-safe-area-context 의 insets 도 그대로다). UIKit 은 iOS 26 부터
/// `UIView.LayoutRegion` 의 corner adaptation 으로 이 모서리를 피한 영역을 알려 준다.
/// 헤더처럼 맨 위에 한 줄로 놓인 버튼은 `.horizontal`(모서리를 옆으로 피하기)을 쓴다.
///
/// 창 전체를 덮는 보이지 않는 측정용 뷰를 창 맨 뒤에 붙여 그 값을 잰다.
public class WindowControlsModule: Module {
  private static let zero: [String: Double] = ["left": 0, "right": 0]

  private let lock = NSLock()
  private var current = WindowControlsModule.zero
  private var probe: WindowControlsProbeView?

  public func definition() -> ModuleDefinition {
    Name("WindowControls")

    Events("onChange")

    // JS 가 처음 그릴 때 쓰는 마지막 측정값. 이후 변화는 onChange 로 보낸다.
    Function("getInsets") { () -> [String: Double] in
      self.lock.lock()
      defer { self.lock.unlock() }
      return self.current
    }

    // 모듈이 만들어질 때 붙여 두면 첫 화면을 그리기 전에 값이 준비된다.
    OnCreate {
      DispatchQueue.main.async { self.attach(retries: 10) }
    }

    OnStartObserving {
      DispatchQueue.main.async { self.attach(retries: 10) }
    }

    OnDestroy {
      DispatchQueue.main.async {
        self.probe?.removeFromSuperview()
        self.probe = nil
      }
    }
  }

  private func attach(retries: Int) {
    if let probe, probe.window != nil {
      probe.setNeedsLayout()
      return
    }
    probe?.removeFromSuperview()
    probe = nil

    // JS 가 막 뜬 순간에는 창이 아직 없을 수 있다 — 잠시 뒤 다시 본다.
    guard let window = Self.appWindow() else {
      if retries > 0 {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
          self.attach(retries: retries - 1)
        }
      }
      return
    }

    let view = WindowControlsProbeView(frame: window.bounds)
    view.onChange = { [weak self] left, right in self?.update(left: left, right: right) }
    window.insertSubview(view, at: 0)
    probe = view
  }

  private func update(left: CGFloat, right: CGFloat) {
    let value: [String: Double] = ["left": Double(left), "right": Double(right)]
    lock.lock()
    current = value
    lock.unlock()
    sendEvent("onChange", value)
  }

  /// 앱 화면이 그려지는 창. 키보드·알림 같은 시스템 창은 windowLevel 이 달라 걸러진다.
  private static func appWindow() -> UIWindow? {
    let windows = UIApplication.shared.connectedScenes
      .compactMap { $0 as? UIWindowScene }
      .flatMap { $0.windows }
      .filter { $0.windowLevel == .normal && !$0.isHidden }
    return windows.first { $0.isKeyWindow } ?? windows.first
  }
}

/// 창 크기 그대로 붙어 창 버튼 폭을 재는 뷰. 터치·접근성에서 빠지고 아무것도 그리지 않는다.
final class WindowControlsProbeView: UIView {
  var onChange: ((CGFloat, CGFloat) -> Void)?
  private var reported: (left: CGFloat, right: CGFloat)?

  override init(frame: CGRect) {
    super.init(frame: frame)
    isUserInteractionEnabled = false
    backgroundColor = .clear
    autoresizingMask = [.flexibleWidth, .flexibleHeight]
    accessibilityElementsHidden = true

    #if compiler(>=6.2)
    if #available(iOS 26.0, *) {
      // 모서리를 피한 가이드에 빈 뷰를 묶어 둔다. 창 버튼이 나타나거나 사라져 가이드가 바뀌면
      // 오토레이아웃이 이 뷰를 다시 배치하면서 layoutSubviews 가 불린다(창 크기가 그대로여도).
      let guide = layoutGuide(for: .safeArea(cornerAdaptation: .horizontal))
      let pin = UIView()
      pin.translatesAutoresizingMaskIntoConstraints = false
      pin.isUserInteractionEnabled = false
      pin.isHidden = true
      addSubview(pin)
      NSLayoutConstraint.activate([
        pin.topAnchor.constraint(equalTo: guide.topAnchor),
        pin.leadingAnchor.constraint(equalTo: guide.leadingAnchor),
        pin.trailingAnchor.constraint(equalTo: guide.trailingAnchor),
        pin.bottomAnchor.constraint(equalTo: guide.bottomAnchor),
      ])
    }
    #endif
  }

  required init?(coder: NSCoder) {
    fatalError("init(coder:) is not supported")
  }

  override func safeAreaInsetsDidChange() {
    super.safeAreaInsetsDidChange()
    setNeedsLayout()
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    let value = measure()
    if let reported, reported == value { return }
    reported = value
    onChange?(value.left, value.right)
  }

  /// 창 버튼 때문에 평소 안전영역보다 더 들어가야 하는 폭(좌, 우).
  ///
  /// corner adaptation 은 창 버튼뿐 아니라 **화면 모서리 곡률도** 피한다 — 아이폰 17 Pro 세로에서
  /// 좌우 18pt, iPad 전체 화면에서 9pt 씩 돌려준다. 그대로 쓰면 폰 헤더가 밀리므로, 좌우에 똑같이
  /// 붙는 곡률 몫은 빼고 한쪽에만 있는 창 버튼 몫(창 모드 iPad 에서 66 − 9.5 = 56.5pt)만 남긴다.
  private func measure() -> (left: CGFloat, right: CGFloat) {
    #if compiler(>=6.2)
    if #available(iOS 26.0, *), window != nil {
      let safe = safeAreaInsets
      let adapted = edgeInsets(for: .safeArea(cornerAdaptation: .horizontal))
      let left = max(0, adapted.left - safe.left)
      let right = max(0, adapted.right - safe.right)
      return (max(0, left - right), max(0, right - left))
    }
    #endif
    return (0, 0)
  }
}
