import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // 인스타 프로필 링크용 짧은 주소. 인스타는 링크가 하나면 제목 대신 URL 을
      // 그대로 보여 줘서 /get?src=instagram 은 잘린다. 주소창은 /ig 그대로 두고
      // /get 을 src=instagram 으로 연다(리다이렉트 한 번이 늘지 않는다).
      { source: "/ig", destination: "/get?src=instagram" },
    ];
  },
};

export default nextConfig;
