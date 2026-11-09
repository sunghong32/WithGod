const {
  AndroidConfig,
  CodeGenerator,
  XML,
  createRunOncePlugin,
  withAndroidManifest,
  withDangerousMod,
  withMainActivity,
} = require('expo/config-plugins');

/**
 * 안드로이드에서 세로 고정을 폰에만 건다(이슈 #26).
 *
 * app.json 의 `orientation: "portrait"` 는 MainActivity 에 android:screenOrientation="portrait"
 * 를 써서 태블릿·펼친 폴더블까지 세로로 묶는다. Play Console 은 이를 "크기 조절 및 방향 제한
 * 삭제" 권장 조치로 경고하고, Android 16(targetSdk 36)은 가장 짧은 변이 600dp 이상인 화면에서
 * 이미 무시한다. 그런데 Expo 의 orientation 은 화면 크기별로 나눌 수 없고, iOS(아이폰 세로
 * 고정)도 같은 값을 쓰므로 app.json 은 그대로 둔다.
 *
 * 그래서 안드로이드만 이렇게 바꾼다.
 * 1. 매니페스트에서 MainActivity 의 android:screenOrientation 을 지운다(제한 없음).
 * 2. res/values/bools.xml 에 withgod_portrait_only=true, res/values-sw600dp/bools.xml 에 false.
 * 3. MainActivity 가 이 값을 읽어 폰이면 세로로 고정하고, sw600dp 이상이면 풀어 둔다.
 *    onCreate 에서 한 번, 창 구성이 바뀔 때마다(onConfigurationChanged) 다시 — 폴더블을
 *    접고 펴도 액티비티가 새로 만들어지지 않는 경우(configChanges 에 smallestScreenSize)를 위해서다.
 *
 * 판정은 창 기준이라 태블릿 분할 화면에서 창이 600dp 보다 좁으면 세로를 요청한다. 그래도
 * 지금(모든 창에서 세로 고정)보다 제한이 늘어나는 경우는 없다.
 */
const PLUGIN_NAME = 'with-phone-only-portrait';
const BOOL_NAME = 'withgod_portrait_only';
const BOOL_VALUES = [
  { kind: 'values', value: 'true' },
  { kind: 'values-sw600dp', value: 'false' },
];

const ORIENTATION_POLICY = `  // ${PLUGIN_NAME}: 폰(sw600dp 미만)은 세로 고정, 태블릿·펼친 폴더블은 제한 없음.
  private fun applyOrientationPolicy() {
    val desired = if (resources.getBoolean(R.bool.${BOOL_NAME})) {
      android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
    } else {
      android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
    }
    if (requestedOrientation != desired) {
      requestedOrientation = desired
    }
  }

  override fun onConfigurationChanged(newConfig: android.content.res.Configuration) {
    super.onConfigurationChanged(newConfig)
    applyOrientationPolicy()
  }`;

const withoutManifestOrientation = (config) =>
  withAndroidManifest(config, (cfg) => {
    const mainActivity = AndroidConfig.Manifest.getMainActivityOrThrow(cfg.modResults);
    delete mainActivity.$['android:screenOrientation'];
    return cfg;
  });

const withPortraitOnlyBools = (config) =>
  withDangerousMod(config, [
    'android',
    async (cfg) => {
      for (const { kind, value } of BOOL_VALUES) {
        const path = await AndroidConfig.Paths.getResourceXMLPathAsync(
          cfg.modRequest.projectRoot,
          { kind, name: 'bools' },
        );
        const xml = await AndroidConfig.Resources.readResourcesXMLAsync({ path });
        const others = (xml.resources.bool ?? []).filter((item) => item.$?.name !== BOOL_NAME);
        xml.resources.bool = [
          ...others,
          AndroidConfig.Resources.buildResourceItem({ name: BOOL_NAME, value }),
        ];
        await XML.writeXMLAsync({ path, xml });
      }
      return cfg;
    },
  ]);

const withOrientationPolicyInMainActivity = (config) =>
  withMainActivity(config, (cfg) => {
    if (cfg.modResults.language !== 'kt') {
      throw new Error(`[${PLUGIN_NAME}] MainActivity 가 Kotlin 이 아닙니다(${cfg.modResults.language}).`);
    }
    let contents = cfg.modResults.contents;
    contents = CodeGenerator.mergeContents({
      src: contents,
      newSrc: ORIENTATION_POLICY,
      tag: `${PLUGIN_NAME}-policy`,
      anchor: /^class MainActivity\b/,
      offset: 1,
      comment: '  //',
    }).contents;
    // 첫 화면이 그려지기 전에 정하도록 super.onCreate 보다 먼저 부른다.
    contents = CodeGenerator.mergeContents({
      src: contents,
      newSrc: '    applyOrientationPolicy()',
      tag: `${PLUGIN_NAME}-oncreate`,
      anchor: /^\s*super\.onCreate\(/,
      offset: 0,
      comment: '    //',
    }).contents;
    cfg.modResults.contents = contents;
    return cfg;
  });

const withPhoneOnlyPortrait = (config) => {
  config = withoutManifestOrientation(config);
  config = withPortraitOnlyBools(config);
  config = withOrientationPolicyInMainActivity(config);
  return config;
};

module.exports = createRunOncePlugin(withPhoneOnlyPortrait, PLUGIN_NAME, '1.0.0');
