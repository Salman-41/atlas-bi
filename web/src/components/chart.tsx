"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
export default function Chart({
  labels,
  values,
  type = "line",
  label = "Purchase value",
  dark = false,
}: {
  labels: string[];
  values: number[];
  type?: "line" | "bar";
  label?: string;
  dark?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const muted = dark ? "#939ebd" : "#a0a7bc";
    chart.setOption({
      color: ["#8c78ea"],
      animationDuration: 450,
      tooltip: {
        trigger: "axis",
        backgroundColor: dark ? "#252b42" : "#fff",
        borderColor: dark ? "#3b425b" : "#e9e6f3",
        padding: [12, 16],
        textStyle: { color: dark ? "#e9e7ff" : "#4b4567", fontSize: 11 },
        valueFormatter: (v: number) =>
          v.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        axisPointer: {
          type: "line",
          lineStyle: { color: "#a89bd7", type: "dashed" },
        },
      },
      grid: { left: 62, right: 28, top: 24, bottom: 43 },
      xAxis: {
        type: "category",
        boundaryGap: type === "bar",
        data: labels,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: muted,
          hideOverlap: true,
          fontSize: 10,
          margin: 18,
          formatter: (v: string) =>
            /^\d{4}-\d{2}-\d{2}$/.test(v)
              ? new Date(v + "T00:00:00Z").toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC",
                })
              : v,
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: muted,
          fontSize: 10,
          formatter: (v: number) =>
            Math.abs(v) >= 1000000
              ? `${v / 1000000}m`
              : Math.abs(v) >= 1000
                ? `${v / 1000}k`
                : String(v),
        },
        splitLine: {
          lineStyle: { color: dark ? "#30364b" : "#eef0f6", type: "dashed" },
        },
      },
      series: [
        {
          name: label,
          type,
          data: values,
          smooth: 0.28,
          symbol: "circle",
          symbolSize: 7,
          showSymbol: false,
          lineStyle: { width: 3, color: "#8c78ea" },
          areaStyle:
            type === "line"
              ? {
                  color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: dark ? "#8c78ea35" : "#8c78ea28" },
                    { offset: 1, color: "#8c78ea00" },
                  ]),
                }
              : undefined,
          barMaxWidth: 34,
          itemStyle: { borderRadius: [6, 6, 0, 0] },
        },
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [labels, values, type, label, dark]);
  return (
    <div
      ref={ref}
      className="chart"
      role="img"
      aria-label={`${label} chart with ${labels.length} observations`}
    />
  );
}
