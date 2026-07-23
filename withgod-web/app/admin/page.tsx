import type { Metadata } from "next";

import { Dashboard } from "./Dashboard";

export const metadata: Metadata = {
  title: "WithGod 지표",
};

export default function AdminPage() {
  return <Dashboard />;
}
