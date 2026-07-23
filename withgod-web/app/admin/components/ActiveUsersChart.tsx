"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/lib/analytics";

import { ChartTooltip, axisProps, formatDayShort, formatNumber } from "./chartPrimitives";

/**
 * 일별 활성 사용자.
 *
 * 신규 + 재방문 = DAU 라서 누적 막대 하나로 세 지표를 다 보여준다. DAU 선을
 * 따로 겹쳐 그리면 같은 값을 두 번 그리는 셈이라 읽기만 어려워진다.
 */
export function ActiveUsersChart({ data }: { data: DailyPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDayShort}
          minTickGap={24}
          {...axisProps}
        />
        <YAxis allowDecimals={false} tickFormatter={formatNumber} {...axisProps} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          content={<ChartTooltip showTotal />}
        />
        {/* stroke 는 테두리가 아니라 표면색 2px 간격 — 누적 조각을 떼어놓는 역할 */}
        <Bar
          dataKey="returning_users"
          name="재방문"
          stackId="dau"
          fill="var(--series-1)"
          stroke="var(--surface-1)"
          strokeWidth={2}
          maxBarSize={24}
        />
        <Bar
          dataKey="new_users"
          name="신규"
          stackId="dau"
          fill="var(--series-2)"
          stroke="var(--surface-1)"
          strokeWidth={2}
          maxBarSize={24}
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
