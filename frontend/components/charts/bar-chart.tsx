"use client";

import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { formatCompact } from "@/lib/utils";

interface BarChartDataItem {
  name: string;
  value: number;
  color?: string;
}

interface BarChartProps {
  data: BarChartDataItem[];
  height?: number;
  formatY?: (value: number) => string;
  defaultColor?: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  youtube: "#ef4444",
  instagram: "#ec4899",
  linkedin: "#2563eb",
  tiktok: "#171717",
};

export function BarChart({
  data,
  height = 250,
  formatY = formatCompact,
  defaultColor = "hsl(var(--primary))",
}: BarChartProps) {
  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBarChart
        data={data}
        margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={formatY} width={50} />
        <Tooltip
          formatter={(value: number) => [formatY(value), "Videos"]}
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "var(--radius)",
            fontSize: 12,
          }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((entry, idx) => (
            <Cell
              key={idx}
              fill={
                entry.color ||
                PLATFORM_COLORS[entry.name.toLowerCase()] ||
                defaultColor
              }
            />
          ))}
        </Bar>
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
