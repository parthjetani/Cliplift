"use client";

import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { formatCompact } from "@/lib/utils";

interface LineChartProps<T extends object> {
  data: T[];
  xKey: keyof T & string;
  yKey: keyof T & string;
  color?: string;
  height?: number;
  formatX?: (value: string) => string;
  formatY?: (value: number) => string;
  yLabel?: string;
}

export function LineChart<T extends object>({
  data,
  xKey,
  yKey,
  color = "hsl(var(--primary))",
  height = 300,
  formatX,
  formatY = formatCompact,
  yLabel,
}: LineChartProps<T>) {
  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsLineChart
        data={data}
        margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 12 }}
          tickFormatter={formatX}
          className="text-muted-foreground"
        />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={formatY}
          label={
            yLabel
              ? { value: yLabel, angle: -90, position: "insideLeft", fontSize: 12 }
              : undefined
          }
          className="text-muted-foreground"
          width={60}
        />
        <Tooltip
          formatter={(value: number) => [formatY(value), yLabel || yKey]}
          labelFormatter={formatX}
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "var(--radius)",
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey={yKey}
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </RechartsLineChart>
    </ResponsiveContainer>
  );
}
