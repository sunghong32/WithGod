const { createRunOncePlugin, withPodfile } = require('expo/config-plugins');

const PLUGIN_NAME = 'with-rnfirebase-static-framework';
const STATIC_FRAMEWORK_FLAG = '$RNFirebaseAsStaticFramework = true';

const POST_INSTALL_MARKER =
  '# with-rnfirebase-static-framework: allow non-modular includes';
const POST_INSTALL_SNIPPET = `    ${POST_INSTALL_MARKER}
    installer.pods_project.targets.each do |t|
      if t.name.start_with?('RNFB') || t.name.start_with?('RNFirebase')
        t.build_configurations.each do |c|
          c.build_settings['CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES'] = 'YES'
        end
      end
    end
    # Xcode 26 Clang과 fmt 11.0의 consteval 비호환 회피.
    # fmt base.h가 FMT_USE_CONSTEVAL을 #ifndef 가드 없이 정의해 매크로 주입이
    # 안 먹히므로 헤더를 직접 패치한다 (pod install 마다 재적용됨).
    fmt_base = File.join(installer.sandbox.root, 'fmt', 'include', 'fmt', 'base.h')
    if File.exist?(fmt_base)
      src = File.read(fmt_base)
      patched = src.gsub('#  define FMT_USE_CONSTEVAL 1', '#  define FMT_USE_CONSTEVAL 0')
      File.write(fmt_base, patched) if patched != src
    end`;

const STANDALONE_POST_INSTALL = `
post_install do |installer|
${POST_INSTALL_SNIPPET}
end
`;

function injectStaticFrameworkFlag(src) {
  if (src.includes(STATIC_FRAMEWORK_FLAG)) {
    return src;
  }

  const prepareProjectPattern = /^(\s*prepare_react_native_project!\s*)$/m;
  if (prepareProjectPattern.test(src)) {
    return src.replace(
      prepareProjectPattern,
      `$1\n\n${STATIC_FRAMEWORK_FLAG}`
    );
  }

  const firstTargetPattern = /^(\s*target\s+['"].+['"]\s+do\s*)$/m;
  if (firstTargetPattern.test(src)) {
    return src.replace(firstTargetPattern, `${STATIC_FRAMEWORK_FLAG}\n\n$1`);
  }

  return src;
}

function mergePostInstallHook(src) {
  if (src.includes(POST_INSTALL_MARKER)) {
    return src;
  }

  const existingHookPattern = /(post_install\s+do\s*\|\s*installer\s*\|\s*\n)/m;
  if (existingHookPattern.test(src)) {
    return src.replace(existingHookPattern, `$1${POST_INSTALL_SNIPPET}\n`);
  }

  return `${src.trimEnd()}\n${STANDALONE_POST_INSTALL}`;
}

function removeLegacyAppendedBlock(src) {
  return src.replace(
    /\n?post_install do \|installer\|\n\s*# with-rnfirebase-static-framework: allow non-modular includes\n(?:.*\n)*?end\s*$/m,
    ''
  );
}

function removeLegacyModularHeadersFlag(src) {
  return src.replace(/^\s*use_modular_headers!\s*$/gm, '');
}

function patchPodfile(src) {
  let next = src;
  next = removeLegacyModularHeadersFlag(next);
  next = removeLegacyAppendedBlock(next);
  next = injectStaticFrameworkFlag(next);
  next = mergePostInstallHook(next);
  return next;
}

const withRNFirebaseStaticFramework = (config) =>
  withPodfile(config, (config) => {
    config.modResults.contents = patchPodfile(config.modResults.contents);
    return config;
  });

module.exports = createRunOncePlugin(
  withRNFirebaseStaticFramework,
  PLUGIN_NAME,
  '1.0.0'
);
