export const verseKeys = {
  all: ["verse"] as const,
  // 날짜(KST)와 언어를 키에 포함해 자정·언어 변경 시 새 데이터를 받아오게 한다.
  daily: (date: string, lang: string) =>
    [...verseKeys.all, "daily", date, lang] as const,
};
