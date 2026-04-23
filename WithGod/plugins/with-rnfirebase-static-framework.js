const { createRunOncePlugin, withPodfile } = require('expo/config-plugins');

const PLUGIN_NAME = 'with-rnfirebase-static-framework';
const STATIC_FRAMEWORK_FLAG = '$RNFirebaseAsStaticFramework = true';
const MODULAR_HEADERS_FLAG = 'use_modular_headers!';

function injectFlag(src, flag) {
  if (src.includes(flag)) {
    return src;
  }

  const prepareProjectPattern = /^(\s*prepare_react_native_project!\s*)$/m;
  if (prepareProjectPattern.test(src)) {
    return src.replace(prepareProjectPattern, `$1\n\n${flag}`);
  }

  const firstTargetPattern = /^(\s*target\s+['"].+['"]\s+do\s*)$/m;
  if (firstTargetPattern.test(src)) {
    return src.replace(firstTargetPattern, `${flag}\n\n$1`);
  }

  return src;
}

function patchPodfile(src) {
  let next = src;
  next = injectFlag(next, STATIC_FRAMEWORK_FLAG);
  next = injectFlag(next, MODULAR_HEADERS_FLAG);
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
