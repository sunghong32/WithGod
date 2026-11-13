/**
 * 기기 현지 날짜(YYYY-MM-DD).
 *
 * 오늘의 말씀은 이 날짜로 고른다(#69) — 서버에 기기 날짜를 보내면 그날 말씀을 주므로
 * 나라마다 각자의 자정에 바뀐다. (전에는 한국 날짜라 미국 동부에서는 오전 10시에 바뀌었다.)
 */
export function localToday(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
