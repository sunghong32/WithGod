"use client";

import { useEffect } from "react";

/**
 * iPadOS 13+ 사파리는 Mac 의 User-Agent 를 보내서 서버가 iPad 를 알아보지
 * 못한다. 터치 지점이 여럿인 "Mac" 은 iPad 이므로 여기서 App Store 로 보낸다.
 */
export default function IpadRedirect({ href }: { href: string }) {
  useEffect(() => {
    const looksLikeMac = /Macintosh/.test(navigator.userAgent);
    if (looksLikeMac && navigator.maxTouchPoints > 1) {
      window.location.replace(href);
    }
  }, [href]);
  return null;
}
