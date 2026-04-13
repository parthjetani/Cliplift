"use client";

import {
  AreaChart as RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { formatCompact } from "@/lib/utils";

interface AreaChartProps<T extends object> {
  data: T[];
  xKey: keyof T & string;
  yKey: keyof T & string;
  color?: string;
  height?: number;
  formatX?: (value: string) => string;
  formatY?: (value: number) => string;
  yLabel?: string;
}

export function AreaChart<T extends object>({
  data,
  xKey,
  yKey,
  color = "hsl(222.2 47.4% 11.2%)",
  height = 300,
  formatX,
  formatY = formatCompact,
  yLabel,
}: AreaChartProps<T>) {
  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsAreaChart
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
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={color}
          fill={color}
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RechartsAreaChart>
    </ResponsiveContainer>
  );
}
