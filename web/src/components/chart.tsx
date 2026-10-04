"use client";
import { useEffect, useMemo, useRef, useState } from "react";
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
  const [view, setView] = useState("Daily");
  const [average, setAverage] = useState(true);
  const series = useMemo(() => {
    if (type === "bar" || view === "Daily") return { labels, values };
    if (view === "Cumulative") {
      let total = 0;
      return { labels, values: values.map((v) => (total += v)) };
    }
    const groups = new Map<string, number>();
    labels.forEach((d, i) => {
      const date = new Date(d + "T00:00:00Z");
      date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
      const key = date.toISOString().slice(0, 10);
      groups.set(key, (groups.get(key) || 0) + values[i]);
    });
    return { labels: [...groups.keys()], values: [...groups.values()] };
  }, [labels, values, type, view]);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const muted = dark ? "#8799b0" : "#8390a5";
    const showAverage = type === "line" && view === "Daily" && average;
    const rolling = series.values.map((_, i) =>
      i < 6
        ? null
        : series.values.slice(i - 6, i + 1).reduce((a, b) => a + b, 0) / 7,
    );
    chart.setOption({
      color: ["#5ce6bf", "#b2a4ff"],
      animationDuration: 350,
      tooltip: {
        trigger: "axis",
        backgroundColor: dark ? "#1b2536" : "#fff",
        borderColor: dark ? "#344158" : "#e1e6ed",
        padding: [12, 16],
        textStyle: { color: dark ? "#e1edf7" : "#293449", fontSize: 11 },
        valueFormatter: (v: number) =>
          typeof v === "number"
            ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
            : "—",
        axisPointer: {
          type: "line",
          lineStyle: { color: "#73968b", type: "dashed" },
        },
      },
      toolbox: {
        right: 20,
        top: 0,
        iconStyle: { borderColor: muted },
        feature: {
          saveAsImage: {
            title: "Save chart as PNG",
            name: "atlas-" + label.toLowerCase().replaceAll(" ", "-"),
            backgroundColor: dark ? "#101a28" : "#fff",
            pixelRatio: 2,
          },
          dataZoom: { title: { zoom: "Select a range", back: "Reset range" } },
        },
      },
      grid: { left: 64, right: 28, top: 34, bottom: type === "line" ? 68 : 40 },
      xAxis: {
        type: "category",
        boundaryGap: type === "bar",
        data: series.labels,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: muted,
          hideOverlap: true,
          fontSize: 10,
          margin: 14,
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
          lineStyle: { color: dark ? "#253348" : "#eaf0f5", type: "dashed" },
        },
      },
      dataZoom:
        type === "line"
          ? [
              { type: "inside" },
              {
                type: "slider",
                height: 14,
                bottom: 12,
                borderColor: "transparent",
                backgroundColor: dark ? "#1a2839" : "#edf4f1",
                fillerColor: "#5ce6bf16",
                handleStyle: { color: "#55cba7", borderColor: "#55cba7" },
                dataBackground: {
                  lineStyle: { color: "#5ce6bf" },
                  areaStyle: { color: "#5ce6bf22" },
                },
                textStyle: { color: muted, fontSize: 9 },
              },
            ]
          : [],
      series: [
        {
          name: label,
          type,
          data: series.values,
          smooth: false,
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          lineStyle: { width: 2.5, color: "#5ce6bf" },
          areaStyle:
            type === "line"
              ? {
                  color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: "#5ce6bf30" },
                    { offset: 1, color: "#5ce6bf00" },
                  ]),
                }
              : undefined,
          barMaxWidth: 34,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
        ...(showAverage
          ? [
              {
                name: "7-day moving average",
                type: "line",
                data: rolling,
                showSymbol: false,
                lineStyle: { width: 2, type: "dashed", color: "#b2a4ff" },
              },
            ]
          : []),
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [series, type, label, dark, view, average]);
  return (
    <div className="chart-module">
      {type === "line" && (
        <div className="chart-view-controls">
          <div className="chart-switch">
            {["Daily", "Weekly", "Cumulative"].map((v) => (
              <button
                key={v}
                className={view === v ? "selected" : ""}
                onClick={() => setView(v)}
              >
                {v}
              </button>
            ))}
          </div>
          {view === "Daily" && (
            <label>
              <input
                type="checkbox"
                checked={average}
                onChange={(e) => setAverage(e.target.checked)}
              />
              <span />
              7-day average
            </label>
          )}
        </div>
      )}
      <div
        ref={ref}
        className="chart"
        role="img"
        aria-label={`${label} chart: ${view.toLowerCase()}, ${series.labels.length} observations`}
      />
    </div>
  );
}
