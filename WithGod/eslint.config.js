// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*'],
  },
  {
    // 컴포넌트에서는 전역 t 를 쓰지 않는다(이슈 #30).
    // React Compiler 는 모듈에서 가져온 함수를 "변하지 않는 값"으로 보고, 그 호출로 만든
    // 렌더 결과를 캐시해 다시 쓴다. 전역 t 는 현재 언어(바뀌는 전역 상태)를 읽으므로
    // 언어를 바꿔도 처음 그린 문구가 그대로 남는다. useTranslation() 의 t 는 언어가
    // 바뀔 때마다 새 함수라 캐시가 함께 무효화된다.
    // 위젯(src/widgets)은 React 렌더러 밖에서 순수 함수로 불려 해당이 없다.
    files: ['src/**/*.tsx'],
    ignores: ['src/widgets/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@/shared/lib/i18n',
              importNames: ['t'],
              message:
                '컴포넌트에서는 useTranslation() 의 t 를 쓰세요. 전역 t 로 그린 문구는 React Compiler 캐시 때문에 언어를 바꿔도 안 바뀝니다(이슈 #30). 렌더 밖(한 번만 등록되는 이벤트 핸들러 등)에서 호출 시점 언어가 필요하면 eslint-disable 에 이유를 적으세요.',
            },
          ],
        },
      ],
    },
  },
]);
