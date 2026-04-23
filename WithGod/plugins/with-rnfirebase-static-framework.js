const { createRunOncePlugin, withPodfile } = require('expo/config-plugins');

const PLUGIN_NAME = 'with-rnfirebase-static-framework';
const STATIC_FRAMEWORK_FLAG = '$RNFirebaseAsStaticFramework = true';

const POST_INSTALL_MARKER = '# with-rnfirebase-static-framework: allow non-modular includes';
const POST_INSTALL_BLOCK = `
post_install do |installer|
  ${POST_INSTALL_MARKER}
  installer.pods_project.targets.each do |target|
    if target.name.start_with?('RNFB') || target.name.start_with?('RNFirebase')
      target.build_configurations.each do |config|
        config.build_settings['CLANG_ALLOW_NON_MODULAR_INCLUDES_IN_FRAMEWORK_MODULES'] = 'YES'
      end
    end
  end
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

function injectPostInstallHook(src) {
  if (src.includes(POST_INSTALL_MARKER)) {
    return src;
  }
  return `${src.trimEnd()}\n${POST_INSTALL_BLOCK}`;
}

function removeLegacyModularHeadersFlag(src) {
  return src.replace(/^\s*use_modular_headers!\s*$/gm, '');
}

function patchPodfile(src) {
  let next = src;
  next = removeLegacyModularHeadersFlag(next);
  next = injectStaticFrameworkFlag(next);
  next = injectPostInstallHook(next);
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
