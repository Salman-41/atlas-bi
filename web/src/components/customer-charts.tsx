"use client";
import dynamic from "next/dynamic";
import { Card } from "./ui/card";
const Viz = dynamic(() => import("./viz"), {
  ssr: false,
  loading: () => <div className="skeleton chart" />,
});
type Cohort = { cohort: string; month_index: number; customers: number };
type Profile = {
  profile: number;
  recency: number;
  frequency: number;
  monetary: number;
};
export default function CustomerCharts({
  cohorts,
  profiles,
  dark,
}: {
  cohorts: Cohort[];
  profiles: Profile[];
  dark: boolean;
}) {
  const labels = Array.from(new Set(cohorts.map((r) => r.cohort.slice(0, 7))));
  const months = Array.from(new Set(cohorts.map((r) => r.month_index))).sort(
    (a, b) => a - b,
  );
  const bases = new Map(
    cohorts
      .filter((r) => r.month_index === 0)
      .map((r) => [r.cohort, r.customers]),
  );
  const cells = cohorts
    .filter((r) => bases.has(r.cohort))
    .map((r) => [
      months.indexOf(r.month_index),
      labels.indexOf(r.cohort.slice(0, 7)),
      Number(((r.customers / bases.get(r.cohort)!) * 100).toFixed(1)),
    ]);
  return (
    <div className="analysis-grid customer-plots">
      <Card>
        <div className="card-heading">
          <div>
            <span className="eyebrow">MONTHLY COHORTS</span>
            <h2>Retention across purchase cohorts</h2>
          </div>
        </div>
        {cells.length ? (
          <Viz
            dark={dark}
            title="Monthly purchase cohort retention"
            option={{
              tooltip: {
                position: "top",
                formatter: (params: unknown) => {
                  const p = params as { value: number[] };
                  return `${labels[p.value[1]]} · Month ${months[p.value[0]]}<br/>${p.value[2]}% observed purchasing retention`;
                },
              },
              grid: { left: 75, right: 35, top: 30, bottom: 65 },
              xAxis: {
                type: "category",
                data: months.map((m) => `M${m}`),
                axisLine: { show: false },
                axisTick: { show: false },
              },
              yAxis: {
                type: "category",
                data: labels,
                axisLine: { show: false },
                axisTick: { show: false },
                inverse: true,
              },
              visualMap: {
                min: 0,
                max: 100,
                orient: "horizontal",
                left: "center",
                bottom: 0,
                itemWidth: 10,
                itemHeight: 140,
                inRange: {
                  color: dark
                    ? ["#19263a", "#305f66", "#56e5bc"]
                    : ["#eaf4ef", "#a2d9c7", "#38b68e"],
                },
                textStyle: { color: dark ? "#9caac1" : "#6e7c94" },
              },
              series: [
                {
                  type: "heatmap",
                  data: cells,
                  label: {
                    show: true,
                    formatter: (p: unknown) =>
                      `${(p as { value: number[] }).value[2]}%`,
                    fontSize: 11,
                    color: dark ? "#e6f3ed" : "#245547",
                  },
                  itemStyle: {
                    borderWidth: 4,
                    borderColor: dark ? "#101a28" : "#fff",
                    borderRadius: 4,
                  },
                },
              ],
            }}
          />
        ) : (
          <p className="empty">
            Select a range including the cohort’s first purchase month to
            calculate retention.
          </p>
        )}
        <p className="chart-footnote">
          Cohort = first observed purchase month. Only measured cells are shown;
          missing future months are not zero retention.
        </p>
      </Card>
      <Card>
        <div className="card-heading">
          <div>
            <span className="eyebrow">TOP 100 CUSTOMER PROFILES</span>
            <h2>Frequency meets value</h2>
          </div>
        </div>
        <Viz
          dark={dark}
          title="RFM customer frequency and monetary value"
          option={{
            grid: { left: 65, right: 30, top: 30, bottom: 50 },
            tooltip: {
              trigger: "item",
              formatter: (p: unknown) => {
                const v = (p as { value: number[] }).value;
                return `Profile ${v[3]}<br/>${v[0]} sessions · ${v[1].toFixed(2)} price units<br/>${v[2]} days since latest purchase`;
              },
            },
            xAxis: {
              type: "value",
              name: "Purchase sessions",
              nameLocation: "middle",
              nameGap: 30,
              splitLine: { show: false },
            },
            yAxis: {
              type: "value",
              name: "Price units",
              splitLine: { lineStyle: { color: dark ? "#293548" : "#edf0f6" } },
            },
            series: [
              {
                type: "scatter",
                data: profiles.map((r) => [
                  r.frequency,
                  r.monetary,
                  r.recency,
                  r.profile,
                ]),
                symbolSize: (v: number[]) =>
                  Math.min(25, 8 + Math.sqrt(v[1]) / 10),
                itemStyle: { color: "#a79aff", opacity: 0.7 },
              },
            ],
          }}
        />
        <p className="chart-footnote">
          Profiles are pseudonymous ranks. Bubble size reflects monetary value;
          tooltip includes recency.
        </p>
      </Card>
    </div>
  );
}
