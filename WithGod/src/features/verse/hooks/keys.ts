export const verseKeys = {
  all: ["verse"] as const,
  // 날짜(KST)를 키에 포함해 자정이 지나면 새 데이터를 받아오게 한다.
  daily: (date: string) => [...verseKeys.all, "daily", date] as const,
};
