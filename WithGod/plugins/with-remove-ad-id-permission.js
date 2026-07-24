const { createRunOncePlugin, withAndroidManifest } = require('expo/config-plugins');

/**
 * Firebase Analytics(Google Play Services measurement SDK)는 안드로이드 매니페스트에
 * com.google.android.gms.permission.AD_ID 권한을 자동으로 병합한다. 이 권한이 있으면
 * Play Console 이 "광고 ID 사용" 선언을 요구하는데, 이 앱은 광고를 하지 않고 분석
 * 목적으로만 Firebase 를 쓴다. 광고 ID 는 필요 없으므로 권한을 제거해
 * "광고 ID 미사용 / 추적 없음" 개인정보 방침과 일치시킨다.
 *
 * tools:node="remove" 로 병합 단계에서 해당 권한을 걷어낸다.
 */
const AD_ID_PERMISSION = 'com.google.android.gms.permission.AD_ID';
const PLUGIN_NAME = 'with-remove-ad-id-permission';

const withRemoveAdIdPermission = (config) =>
  withAndroidManifest(config, (cfg) => {
    const manifest = cfg.modResults.manifest;

    // tools 네임스페이스가 없으면 tools:node 속성이 무시되므로 먼저 보장한다.
    manifest.$ = manifest.$ || {};
    if (!manifest.$['xmlns:tools']) {
      manifest.$['xmlns:tools'] = 'http://schemas.android.com/tools';
    }

    manifest['uses-permission'] = manifest['uses-permission'] || [];

    const existing = manifest['uses-permission'].find(
      (perm) => perm.$ && perm.$['android:name'] === AD_ID_PERMISSION,
    );

    if (existing) {
      // 이미 선언돼 있으면 remove 지시만 확실히 달아 준다.
      existing.$['tools:node'] = 'remove';
    } else {
      manifest['uses-permission'].push({
        $: {
          'android:name': AD_ID_PERMISSION,
          'tools:node': 'remove',
        },
      });
    }

    return cfg;
  });

module.exports = createRunOncePlugin(
  withRemoveAdIdPermission,
  PLUGIN_NAME,
  '1.0.0',
);
