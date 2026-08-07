package expo.modules.gestureexclusion

import android.graphics.Rect
import android.os.Build
import android.view.View
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

/**
 * 화면 좌측 가장자리를 **시스템 뒤로가기 제스처에서 넘겨받는다.**
 *
 * 안드로이드 10(제스처 내비게이션)부터 화면 좌우 끝 약 20dp 는 시스템 몫이라,
 * 그 구간에서 시작한 스와이프는 앱까지 내려오지 않는다. 네이티브 드로어
 * (AndroidX DrawerLayout)는 `setSystemGestureExclusionRects` 로 이 구간을
 * 가져와서 맨 끝에서 밀어도 열린다. RN 쪽에는 그 API 바인딩이 없어 직접 만든다.
 *
 * 주의: 시스템은 **가장자리당 총 200dp 높이까지만** 제외를 인정한다(그 이상은
 * 무시된다). 전체 높이를 넘겨도 시스템이 알아서 잘라서 적용하므로, 여기서는
 * 화면 전체를 넘기고 나머지는 시스템 판단에 맡긴다.
 */
class GestureExclusionModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("GestureExclusion")

    /**
     * @param widthDp 좌측에서 가져올 폭(dp)
     * @param enabled false 면 제외 구간을 반납한다(드로어가 열려 있을 때 등)
     */
    AsyncFunction("setLeftEdgeExclusion") { widthDp: Double, enabled: Boolean ->
      // 제스처 내비게이션 이전 버전에는 제외 구간 개념 자체가 없다.
      if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return@AsyncFunction

      val activity = appContext.currentActivity ?: return@AsyncFunction
      activity.runOnUiThread {
        val root: View =
          activity.findViewById(android.R.id.content) ?: activity.window.decorView
        if (!enabled) {
          root.systemGestureExclusionRects = emptyList()
          return@runOnUiThread
        }

        val metrics = activity.resources.displayMetrics
        val widthPx = (widthDp * metrics.density).toInt().coerceAtLeast(1)
        // 레이아웃 전이라 height 가 0일 수 있다 — 그때는 화면 높이로 대체한다.
        val heightPx = if (root.height > 0) root.height else metrics.heightPixels
        root.systemGestureExclusionRects = listOf(Rect(0, 0, widthPx, heightPx))
      }
    }
  }
}
