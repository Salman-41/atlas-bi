"use client";
import dynamic from "next/dynamic";
import { Activity, ArrowUpRight, FlaskConical } from "lucide-react";
import { Card } from "./ui/card";
const Viz = dynamic(() => import("./viz"), {
  ssr: false,
  loading: () => <div className="skeleton chart" />,
});
type Model = {
  status: string;
  reason?: string;
  selected_model?: string;
  metrics?: Record<string, number | Record<string, number>>;
  predictions?: { date: string; prediction: number }[];
  backtest?: {
    date: string;
    actual: number;
    prediction: number;
    baseline: number;
  }[];
  profiles?: {
    segment: number;
    customers: number;
    recency: number;
    frequency: number;
    monetary: number;
  }[];
  limitations?: string[];
  training_customers?: number;
  test_customers?: number;
  flagged_sessions?: number;
  sessions?: number;
  k?: number;
  test_days?: number;
};
export type ModelResponse = {
  status: string;
  models?: {
    trained_at?: string;
    source_rows?: number;
    forecast?: Model;
    churn?: Model;
    segmentation?: Model;
    anomaly?: Model;
  };
};
const number = (v: unknown) =>
  typeof v === "number"
    ? v.toLocaleString("en-US", { maximumFractionDigits: 3 })
    : "—";
export default function ModelBoard({
  data,
  dark,
  demo,
}: {
  data?: ModelResponse;
  dark: boolean;
  demo: boolean;
}) {
  const models = data?.models;
  const forecast = models?.forecast;
  const cards: [string, string, Model | undefined, string, unknown][] = [
    [
      "Forecast",
      "Temporal holdout",
      forecast,
      "Selected baseline / model",
      forecast?.selected_model?.replaceAll("_", " "),
    ],
    [
      "Inactivity prediction",
      "Separated time & customer holdout",
      models?.churn,
      "Held-out ROC-AUC",
      (
        models?.churn?.metrics?.logistic_regression as
          Record<string, number> | undefined
      )?.roc_auc,
    ],
    [
      "Segmentation",
      "Log-transformed RFM",
      models?.segmentation,
      "Silhouette score",
      models?.segmentation?.metrics?.silhouette,
    ],
    [
      "Anomaly review",
      "Isolation Forest",
      models?.anomaly,
      "Flagged session fraction",
      models?.anomaly?.metrics?.flagged_fraction,
    ],
  ];
  return (
    <>
      <div className="model-context">
        <FlaskConical size={18} />
        <span>
          {demo
            ? "Demo mode: no trained model claims"
            : models?.trained_at
              ? `Evaluated ${new Date(models.trained_at).toLocaleDateString("en-US")} · ${number(models.source_rows)} source events`
              : "Connect and train models to inspect measured evidence"}
        </span>
        <span className="chip">Reproducible · Seed 41</span>
      </div>
      <div className="model-grid">
        {cards.map(([title, method, model, label, value]) => (
          <Card className="model-card" key={title}>
            <Activity size={20} />
            <span
              className={`chip ${model?.status === "trained" ? "trained-chip" : ""}`}
            >
              {model?.status === "trained" ? "Evaluated" : "Unavailable"}
            </span>
            <span className="eyebrow">{method}</span>
            <h2>{title}</h2>
            <strong className="model-value">
              {typeof value === "string" ? value : number(value)}
            </strong>
            <small>{label}</small>
            <p>
              {model?.reason ||
                model?.limitations?.[0] ||
                "No verified artifact loaded. Demo mode does not invent model performance."}
            </p>
            {model?.status === "trained" && (
              <details>
                <summary>
                  Method & limitations <ArrowUpRight size={12} />
                </summary>
                <ul>
                  {model.limitations?.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              </details>
            )}
          </Card>
        ))}
      </div>
      {forecast?.status === "trained" && (
        <div className="analysis-grid">
          <Card>
            <div className="card-heading">
              <div>
                <span className="eyebrow">
                  {forecast.test_days}-DAY TEMPORAL HOLDOUT
                </span>
                <h2>Observed vs predicted</h2>
              </div>
            </div>
            {forecast.backtest?.length ? (
              <Viz
                dark={dark}
                title="Forecast temporal holdout evaluation"
                option={{
                  legend: {
                    bottom: 0,
                    textStyle: { color: dark ? "#9cabc3" : "#6d7a93" },
                  },
                  grid: { left: 65, right: 30, top: 25, bottom: 55 },
                  tooltip: { trigger: "axis" },
                  xAxis: {
                    type: "category",
                    data: forecast.backtest.map((r) => r.date.slice(5)),
                    axisLine: { show: false },
                    axisTick: { show: false },
                  },
                  yAxis: {
                    type: "value",
                    splitLine: {
                      lineStyle: { color: dark ? "#293548" : "#edf0f6" },
                    },
                  },
                  series: [
                    {
                      name: "Observed",
                      type: "line",
                      showSymbol: false,
                      data: forecast.backtest.map((r) => r.actual),
                    },
                    {
                      name: "Candidate model",
                      type: "line",
                      showSymbol: false,
                      data: forecast.backtest.map((r) => r.prediction),
                    },
                    {
                      name: "Seasonal baseline",
                      type: "line",
                      showSymbol: false,
                      lineStyle: { type: "dashed" },
                      data: forecast.backtest.map((r) => r.baseline),
                    },
                  ],
                }}
              />
            ) : (
              <p className="empty">
                Retrain to generate holdout chart evidence.
              </p>
            )}
          </Card>
          <Card>
            <div className="card-heading">
              <div>
                <span className="eyebrow">MODEL SELECTION</span>
                <h2>Does complexity earn its place?</h2>
              </div>
            </div>
            <div className="model-metrics">
              {Object.entries(forecast.metrics || {}).map(([name, m]) => (
                <div key={name}>
                  <strong>{name.replaceAll("_", " ")}</strong>
                  <span>
                    MAE <b>{number((m as Record<string, number>).mae)}</b>
                  </span>
                  <span>
                    RMSE <b>{number((m as Record<string, number>).rmse)}</b>
                  </span>
                </div>
              ))}
            </div>
            <p className="chart-footnote">
              Lower error is better. Selection uses holdout MAE; a seasonal
              baseline can outperform a more complex model.
            </p>
          </Card>
        </div>
      )}
      {forecast?.predictions?.length && (
        <Card>
          <div className="card-heading">
            <div>
              <span className="eyebrow">
                14-DAY SCENARIO / AFTER HISTORICAL DATA
              </span>
              <h2>Forecast horizon</h2>
            </div>
            <span className="chip">No confidence interval</span>
          </div>
          <Viz
            dark={dark}
            title="Purchase value forecast after observed history"
            option={{
              grid: { left: 65, right: 30, top: 25, bottom: 40 },
              xAxis: {
                type: "category",
                data: forecast.predictions.map((r) => r.date),
                axisLine: { show: false },
                axisTick: { show: false },
              },
              yAxis: {
                type: "value",
                splitLine: {
                  lineStyle: { color: dark ? "#293548" : "#edf0f6" },
                },
              },
              series: [
                {
                  type: "line",
                  data: forecast.predictions.map((r) => r.prediction),
                  showSymbol: false,
                  lineStyle: { type: "dashed", width: 3 },
                  areaStyle: { opacity: 0.08 },
                },
              ],
            }}
          />
          <p className="chart-footnote">
            This is a forecast after the dataset’s historical cutoff, not a
            forecast for today.
          </p>
        </Card>
      )}
      {models?.segmentation?.profiles?.length && (
        <Card>
          <div className="card-heading">
            <div>
              <span className="eyebrow">EXPLORATORY CLUSTER PROFILES</span>
              <h2>Customer segments without invented labels</h2>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cluster</th>
                  <th>Customers</th>
                  <th>Recency</th>
                  <th>Frequency</th>
                  <th>Monetary value</th>
                </tr>
              </thead>
              <tbody>
                {models.segmentation.profiles.map((r) => (
                  <tr key={r.segment}>
                    <td>Cluster {r.segment + 1}</td>
                    <td>{number(r.customers)}</td>
                    <td>{number(r.recency)} days</td>
                    <td>{number(r.frequency)}</td>
                    <td>{number(r.monetary)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
