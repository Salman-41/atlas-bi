"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";
export default function Viz({
  option,
  title,
  dark = false,
  height = 290,
}: {
  option: EChartsOption;
  title: string;
  dark?: boolean;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    instance.current = chart;
    const observer = new ResizeObserver(() => {
      if (!chart.isDisposed()) chart.resize();
    });
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      instance.current = null;
      chart.getZr().animation.stop();
      chart.dispose();
    };
  }, []);
  useEffect(() => {
    const chart = instance.current;
    if (!chart || chart.isDisposed()) return;
    chart.setOption({
      backgroundColor: "transparent",
      color: ["#56e5bc", "#a79aff", "#65b9ee", "#e9ba85"],
      textStyle: {
        color: dark ? "#8d9bae" : "#737e94",
        fontFamily: "system-ui",
        fontSize: 10,
      },
      animation: false,
      tooltip: {
        trigger: "axis",
        backgroundColor: dark ? "#1b2536" : "#fff",
        borderColor: dark ? "#344158" : "#e1e6ed",
        textStyle: { color: dark ? "#e6edf6" : "#293449", fontSize: 11 },
      },
      toolbox: {
        right: 16,
        top: 5,
        iconStyle: { borderColor: dark ? "#7f91aa" : "#8291a7" },
        feature: {
          saveAsImage: {
            title: "Save chart as PNG",
            name: title,
            backgroundColor: dark ? "#101a28" : "#fff",
            pixelRatio: 2,
          },
        },
      },
      ...option,
    }, {notMerge: true});
  }, [option, title, dark]);
  return (
    <div
      className="viz"
      ref={ref}
      style={{ height }}
      role="img"
      aria-label={title}
    />
  );
}
