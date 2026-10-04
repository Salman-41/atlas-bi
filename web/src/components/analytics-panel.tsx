"use client";
import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  Database,
  Layers,
  ScanLine,
} from "lucide-react";
import { Card } from "./ui/card";
const Viz = dynamic(() => import("./viz"), {
  ssr: false,
  loading: () => <div className="skeleton chart" />,
});
export type Insights = {
  current: Record<string, number>;
  previous: Record<string, number>;
  comparison: { start: string; end: string; available: boolean };
  behavior: { event_type: string; events: number; customers: number }[];
  activity: { date: string; event_type: string; events: number }[];
  heatmap: {
    weekday: number;
    hour: number;
    events: number;
    purchases: number;
  }[];
  brands: { brand: string; purchase_value: number; purchases: number }[];
  acquisition: { new_customers: number; returning_customers: number };
  coverage: {
    observed_days: number;
    selected_days: number;
    branded_events: number;
    categorized_events: number;
    session_events: number;
  };
  dataset: {
    events: number;
    products: number;
    customers: number;
    first_date: string;
    last_date: string;
    sample_rows?: number;
    original_rows?: number;
    sampling?: string;
  };
};
const fmt = (v: number) =>
  v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const compact = (v: number) =>
  Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(v);
function Heading({
  index,
  title,
  subtitle,
}: {
  index: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="card-heading">
      <div>
        <span className="eyebrow">
          {index} / {subtitle}
        </span>
        <h2>{title}</h2>
      </div>
      <span className="plot-indicator" />
    </div>
  );
}
export function DatasetStrip({
  data,
  demo,
}: {
  data?: Insights;
  demo: boolean;
}) {
  return (
    <div className="dataset-strip">
      <span>
        <Database size={15} />
        {demo ? "Illustrative dataset" : "REES46 • Cosmetics commerce"}
      </span>
      <span>
        <b>{data ? compact(data.dataset.events) : "—"}</b> unique events
      </span>
      <span>
        <b>{data ? fmt(data.dataset.products) : "—"}</b> products
      </span>
      <span>
        <b>{data ? compact(data.dataset.customers) : "—"}</b> customers
      </span>
      <span className="dataset-range">
        {data
          ? `${data.dataset.first_date} → ${data.dataset.last_date}`
          : "October 2019 → February 2020"}
      </span>
    </div>
  );
}
export function Comparison({ data }: { data: Insights }) {
  const metrics = [
    ["purchase_value", "Purchase value"],
    ["purchase_sessions", "Purchase sessions"],
    ["active_customers", "Active customers"],
    ["events", "Behavior events"],
  ];
  return (
    <div className="comparison-row">
      {metrics.map(([key, label]) => {
        const previous = data.previous[key];
        const change = previous
          ? ((data.current[key] - previous) / previous) * 100
          : null;
        return (
          <div key={key}>
            <span>{label}</span>
            <strong>{compact(data.current[key])}</strong>
            {data.comparison.available && change !== null ? (
              <small className={change >= 0 ? "positive" : "negative"}>
                {change >= 0 ? (
                  <ArrowUpRight size={12} />
                ) : (
                  <ArrowDownRight size={12} />
                )}{" "}
                {Math.abs(change).toFixed(1)}% <em>vs previous period</em>
              </small>
            ) : (
              <small>Previous period outside observed history</small>
            )}
          </div>
        );
      })}
    </div>
  );
}
export default function AnalyticsPanel({
  data,
  dark = false,
  section = "Overview",
}: {
  data: Insights;
  dark?: boolean;
  section?: string;
}) {
  const [heatMetric, setHeatMetric] = useState<"events" | "purchases">(
    "events",
  );
  const dates = useMemo(
    () => Array.from(new Set(data.activity.map((r) => r.date))),
    [data.activity],
  );
  const daily = useMemo(
    () =>
      new Map(
        data.activity.map((r) => [`${r.date}:${r.event_type}`, r.events]),
      ),
    [data.activity],
  );
  const axis = dark ? "#293548" : "#eaf0f5";
  const grid = { left: 52, right: 28, top: 40, bottom: 50 };
  const stages = ["view", "cart", "purchase"];
  const stageRows = stages.map((stage) => ({
    stage,
    customers:
      data.behavior.find((r) => r.event_type === stage)?.customers || 0,
    events: data.behavior.find((r) => r.event_type === stage)?.events || 0,
  }));
  const max = Math.max(...stageRows.map((r) => r.customers), 1);
  return (
    <div className="analytics-extension">
      {section === "Sales" && <Comparison data={data} />}
      <div className="analysis-grid">
        <Card>
          <Heading
            index="02"
            subtitle="BEHAVIORAL REACH"
            title="From discovery to purchase"
          />
          <div className="behavior-funnel">
            {stageRows.map((r, i) => (
              <div className="funnel-row" key={r.stage}>
                <div>
                  <span className="step-id">0{i + 1}</span>
                  <strong>
                    {["Product views", "Added to cart", "Purchased"][i]}
                  </strong>
                  <b>
                    {fmt(r.customers)}
                    <small>customers</small>
                  </b>
                </div>
                <div className="funnel-track">
                  <span
                    style={{
                      width: `${Math.max(2, (r.customers / max) * 100)}%`,
                    }}
                  />
                </div>
                <small>{fmt(r.events)} observed events</small>
              </div>
            ))}
          </div>
          <p className="chart-footnote">
            Distinct customers at each stage; these groups can overlap. This is
            reach, not a sequential conversion rate.
          </p>
        </Card>
        <Card>
          <Heading
            index="03"
            subtitle="CUSTOMER COMPOSITION"
            title="Who came back?"
          />
          <Viz
            dark={dark}
            height={240}
            title="New and returning purchasing customers"
            option={{
              tooltip: { trigger: "item" },
              legend: {
                bottom: 5,
                textStyle: {
                  color: dark ? "#94a4bd" : "#74849b",
                  fontSize: 10,
                },
              },
              series: [
                {
                  type: "pie",
                  radius: ["56%", "76%"],
                  center: ["50%", "43%"],
                  label: { show: false },
                  itemStyle: {
                    borderRadius: 5,
                    borderWidth: 4,
                    borderColor: dark ? "#101a28" : "#fff",
                  },
                  data: [
                    {
                      name: "First observed purchase",
                      value: data.acquisition.new_customers,
                    },
                    {
                      name: "Returning purchaser",
                      value: data.acquisition.returning_customers,
                    },
                  ],
                },
              ],
              graphic: {
                type: "text",
                left: "center",
                top: "34%",
                style: {
                  text: compact(data.current.purchasing_customers),
                  fontSize: 28,
                  fontWeight: 600,
                  fill: dark ? "#e7edf5" : "#263246",
                },
              },
            }}
          />
          <p className="chart-footnote">
            New means first purchase in the loaded history. Earlier customer
            activity may be unobserved.
          </p>
        </Card>
      </div>
      <div className="analysis-grid wide-left">
        <Card>
          <Heading
            index="04"
            subtitle="TEMPORAL PATTERNS / SOURCE TIMESTAMPS"
            title="When your audience is active"
          />
          <div className="heat-controls">
            <span>Day of week × hour</span>
            <div className="chart-switch">
              <button
                className={heatMetric === "events" ? "selected" : ""}
                onClick={() => setHeatMetric("events")}
              >
                All events
              </button>
              <button
                className={heatMetric === "purchases" ? "selected" : ""}
                onClick={() => setHeatMetric("purchases")}
              >
                Purchases
              </button>
            </div>
          </div>
          <Viz
            dark={dark}
            title="Activity heatmap by weekday and hour"
            height={300}
            option={{
              tooltip: {
                position: "top",
                formatter: (params: unknown) => {
                  const p = params as { value: [number, number, number] };
                  return `${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][p.value[1]]} · ${String(p.value[0]).padStart(2, "0")}:00<br/>${fmt(p.value[2])} ${heatMetric}`;
                },
              },
              grid: { left: 50, right: 25, top: 20, bottom: 70 },
              xAxis: {
                type: "category",
                data: Array.from({ length: 24 }, (_, i) => `${i}h`),
                splitArea: { show: false },
                axisLine: { show: false },
                axisTick: { show: false },
              },
              yAxis: {
                type: "category",
                data: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                axisLine: { show: false },
                axisTick: { show: false },
              },
              visualMap: {
                min: 0,
                max: Math.max(...data.heatmap.map((r) => r[heatMetric]), 1),
                calculable: true,
                orient: "horizontal",
                left: "center",
                bottom: 5,
                itemWidth: 10,
                itemHeight: 180,
                textStyle: { color: dark ? "#8e9db3" : "#738098" },
                inRange: {
                  color: dark
                    ? ["#172638", "#235a60", "#56e5bc"]
                    : ["#eef6f4", "#b2e5d5", "#31b792"],
                },
              },
              series: [
                {
                  type: "heatmap",
                  data: data.heatmap.map((r) => [
                    r.hour,
                    r.weekday,
                    r[heatMetric],
                  ]),
                  itemStyle: {
                    borderWidth: 3,
                    borderColor: dark ? "#101a28" : "#fff",
                    borderRadius: 3,
                  },
                  emphasis: {
                    itemStyle: { shadowBlur: 7, shadowColor: "#56e5bc44" },
                  },
                },
              ],
            }}
          />
        </Card>
        <Card>
          <Heading
            index="05"
            subtitle="DATA OBSERVABILITY"
            title="Know your evidence"
          />
          <div className="quality-bars">
            {[
              [
                "Days with events",
                data.coverage.observed_days,
                data.coverage.selected_days,
              ],
              [
                "Session coverage",
                data.coverage.session_events,
                data.current.events,
              ],
              [
                "Brand coverage",
                data.coverage.branded_events,
                data.current.events,
              ],
              [
                "Category coverage",
                data.coverage.categorized_events,
                data.current.events,
              ],
            ].map(([label, n, total]) => {
              const percent = Number(total)
                ? (Number(n) / Number(total)) * 100
                : 0;
              return (
                <div key={String(label)}>
                  <div>
                    <span>{label}</span>
                    <b>{percent.toFixed(1)}%</b>
                  </div>
                  <div className="track">
                    <div style={{ width: `${percent}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="quality-source">
            <ScanLine size={18} />
            <p>
              Missing categories stay visible. No guessed currencies, margins,
              or order identifiers.
            </p>
          </div>
        </Card>
      </div>
      {section === "Sales" && (
        <div className="analysis-grid wide-left">
          <Card>
            <Heading
              index="06"
              subtitle="DAILY EVENT MIX"
              title="The rhythm behind the numbers"
            />
            <Viz
              dark={dark}
              title="Daily event mix"
              option={{
                grid,
                legend: {
                  bottom: 4,
                  textStyle: {
                    color: dark ? "#8e9db3" : "#738098",
                    fontSize: 10,
                  },
                },
                xAxis: {
                  type: "category",
                  data: dates.map((d) => d.slice(5)),
                  axisLine: { show: false },
                  axisTick: { show: false },
                },
                yAxis: {
                  type: "value",
                  splitLine: { lineStyle: { color: axis, type: "dashed" } },
                },
                dataZoom: [{ type: "inside" }],
                series: ["view", "cart", "purchase", "remove_from_cart"].map(
                  (stage) => ({
                    type: "bar",
                    name: stage,
                    stack: "events",
                    data: dates.map(
                      (date) => daily.get(`${date}:${stage}`) || 0,
                    ),
                    barMaxWidth: 18,
                  }),
                ),
              }}
            />
            <p className="chart-footnote">
              Scroll inside the chart to zoom. Use the download icon to save a
              PNG.
            </p>
          </Card>
          <Card>
            <Heading
              index="07"
              subtitle="BRAND CONTRIBUTION"
              title="Leading brands"
            />
            <div className="brand-ranking">
              {data.brands.slice(0, 7).map((r, i) => (
                <div key={r.brand}>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <strong>{r.brand}</strong>
                  <b>{compact(r.purchase_value)}</b>
                </div>
              ))}
            </div>
            <p className="chart-footnote">
              Ranked by observed purchase-event value.
            </p>
          </Card>
        </div>
      )}
      {section === "Data Explorer" && (
        <Card className="data-profile">
          <Layers size={24} />
          <div>
            <span className="eyebrow">THE DATA BEHIND THE STORY</span>
            <h2>Five months. One traceable event history.</h2>
            <p>
              {fmt(data.dataset.events)} deduplicated behavior events across{" "}
              {fmt(data.dataset.products)} products and{" "}
              {fmt(data.dataset.customers)} customer identifiers.
            </p>
            <p>
              {data.dataset.sample_rows
                ? `${fmt(data.dataset.sample_rows)} sampled raw rows before deduplication. `
                : ""}
              {data.dataset.original_rows
                ? `${fmt(data.dataset.original_rows)} events in the original files.`
                : ""}
            </p>
            <p>
              Sample rule:{" "}
              <code>
                {data.dataset.sampling || "Not provided for this dataset"}
              </code>
            </p>
            <span className="chip">
              REES46 attribution · Event grain · Historical sample
            </span>
          </div>
        </Card>
      )}
    </div>
  );
}
