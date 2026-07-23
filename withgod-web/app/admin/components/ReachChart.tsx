"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/lib/analytics";

import { ChartTooltip, axisProps, formatDayShort, formatNumber } from "./chartPrimitives";

/**
 * 주간/월간 활성 사용자.
 *
 * 둘 다 "사용자 수"라 축을 하나만 쓴다. 크기가 달라도 축을 나누지 않는다 —
 * 이중 축은 두 계열의 교차점을 사실과 다르게 보이게 만든다.
 */
export function ReachChart({ data }: { data: DailyPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDayShort}
          minTickGap={24}
          {...axisProps}
        />
        <YAxis allowDecimals={false} tickFormatter={formatNumber} {...axisProps} />
        <Tooltip content={<ChartTooltip />} />
        <Line
          type="monotone"
          dataKey="wau"
          name="주간(WAU)"
          stroke="var(--series-1)"
          strokeWidth={2}
          dot={false}
          // 표면색 2px 링 — 두 선이 겹치는 지점에서도 점이 묻히지 않는다.
          activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
        />
        <Line
          type="monotone"
          dataKey="mau"
          name="월간(MAU)"
          stroke="var(--series-2)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
