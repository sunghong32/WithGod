const { createRunOncePlugin, withAndroidManifest } = require('expo/config-plugins');

/**
 * MainActivity 의 android:configChanges 에 smallestScreenSize 를 더한다(이슈 #26).
 *
 * Expo 가 만드는 매니페스트에는 screenSize·screenLayout 은 있지만 smallestScreenSize 가
 * 없다. 그래서 창의 가장 짧은 변이 바뀌는 순간 — 폴더블을 접거나 펼 때, 태블릿에서 분할
 * 화면에 들어가거나 나올 때 — 안드로이드가 액티비티를 **부수고 새로 만든다**. 그러면
 * 보던 화면·입력하던 글·받아 오던 말씀이 날아가고 앱이 홈으로 돌아간다(태블릿 에뮬레이터에서
 * 설정 화면 → 창 크기 변경 → 홈으로 초기화 재현).
 *
 * 안드로이드 문서가 멀티 윈도우·폴더블에서 권하는 대로 screenSize·smallestScreenSize·
 * screenLayout·orientation 을 모두 앱이 직접 받게 하면, RN 은 액티비티를 유지한 채
 * 새 창 크기만 JS 로 전달한다(useWindowDimensions 가 갱신된다).
 */
const PLUGIN_NAME = 'with-large-screen-config-changes';
const REQUIRED_CHANGES = ['screenSize', 'smallestScreenSize', 'screenLayout', 'orientation'];

const withLargeScreenConfigChanges = (config) =>
  withAndroidManifest(config, (cfg) => {
    const application = cfg.modResults.manifest.application?.[0];
    const mainActivity = application?.activity?.find(
      (activity) => activity.$?.['android:name'] === '.MainActivity',
    );
    if (!mainActivity) {
      throw new Error(`[${PLUGIN_NAME}] AndroidManifest 에서 .MainActivity 를 찾지 못했습니다.`);
    }

    const current = (mainActivity.$['android:configChanges'] ?? '')
      .split('|')
      .filter(Boolean);
    const missing = REQUIRED_CHANGES.filter((change) => !current.includes(change));
    mainActivity.$['android:configChanges'] = [...current, ...missing].join('|');

    return cfg;
  });

module.exports = createRunOncePlugin(
  withLargeScreenConfigChanges,
  PLUGIN_NAME,
  '1.0.0',
);
