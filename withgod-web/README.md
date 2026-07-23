# withgod-web

WithGod 사용자 지표 어드민 대시보드 (Next.js).

- **배포 주소**: https://withgod-web.vercel.app/admin (Vercel, 프로젝트 `withgod-web`)
- **데이터 출처**: 백엔드 `GET /admin/analytics/*` — 설계와 지표 정의는
  [`backend/docs/analytics.md`](../backend/docs/analytics.md)
- `/` 는 아직 비어 있다. 소개 페이지를 만들면 여기에 넣으면 된다.

## 로컬 실행

```bash
cp .env.example .env.local   # 값을 채운다
npm install
npm run dev                  # http://localhost:3000/admin
```

`.env.local` 이 없으면 로그인이 항상 실패한다(비밀번호가 비어 있으면 잠긴
상태로 두도록 돼 있다). 로컬 백엔드를 볼 땐 `ANALYTICS_API_ORIGIN` 을
`http://127.0.0.1:8000` 으로 바꾼다.

## 배포

```bash
npx vercel deploy --prod
```

환경변수는 Vercel 프로젝트 설정(Production)에 등록돼 있다. 값을 바꾸려면:

```bash
npx vercel env rm ADMIN_PASSWORD production
printf '새비밀번호' | npx vercel env add ADMIN_PASSWORD production
npx vercel deploy --prod        # 환경변수는 재배포해야 반영된다
```

> 배포가 `UNKNOWN` 상태로 멈춰 있으면 이전 배포가 동시 빌드 슬롯을 잡고 있는
> 것이다. `npx vercel remove withgod-web --safe --yes` 로 정리하면 풀린다.

## 보안 구조

- `/admin`, `/api/admin` 은 미들웨어에서 세션 쿠키(HMAC 서명, httpOnly·Secure)로 막는다.
- 백엔드 API 키는 서버 라우트 핸들러에만 있고 브라우저로 내려가지 않는다.
  프록시는 지표 이름과 쿼리 파라미터를 허용 목록으로 제한한다.
- 로그인 실패는 IP 당 15분에 10회까지. 어드민 경로 전체에 `noindex`.
- **Next 버전을 내리지 말 것.** 16.0.1 은 알려진 취약점 때문에 Vercel 이
  배포 자체를 거부한다. 인증을 미들웨어에서 걸고 있어 더욱 그렇다.
