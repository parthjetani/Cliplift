"use client";

import { LineChart, Line, ResponsiveContainer } from "recharts";

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
}

/**
 * Minimal inline chart — no axes, no tooltips, just the line.
 * Used inside stat cards for at-a-glance trends.
 */
export function Sparkline({
  data,
  color = "hsl(var(--primary))",
  height = 40,
  width = 100,
}: SparklineProps) {
  if (data.length < 2) return null;

  const chartData = data.map((value, index) => ({ index, value }));

  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
