import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { FarmerVolumeForecast } from "../api/types";
import { CalendarPick, addDays, todayIso } from "../components/CalendarPick";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { RangeBar } from "../components/RangeBar";
import { Empty, Loading, LoadError } from "../components/Status";
import { productLabel, t, unitOf } from "../i18n/strings";
import { useState } from "react";

function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
}

/** A past day: the estimate that was shared then, and what was bought from farmer groups. */
function FarmerHistory() {
  const [day, setDay] = useState(() => addDays(todayIso(), -1));
  const [bounds, setBounds] = useState<{ first: string; last: string } | null>(
    null,
  );
  const { state, reload } = useLoad(async () => {
    const view = await api.farmerDay(day);
    setBounds({ first: view.first_day, last: view.last_day });
    return view;
  }, day);
  const max =
    state.status === "ready"
      ? Math.max(1, ...state.data.rows.map((r) => r.estimate?.high ?? 0))
      : 1;
  return (
    <details className="card farmer-history">
      <summary>
        <Icon name="calendar" size={24} /> {t("farmer.history")}
      </summary>
      <p className="small">{t("farmer.histNote")}</p>
      <CalendarPick
        value={day}
        min={bounds?.first ?? day}
        max={bounds?.last ?? day}
        onChange={setDay}
      />
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <LoadError onRetry={reload} />}
      {state.status === "ready" && !state.data.rows.length && (
        <p className="notice">{t("farmer.histNone")}</p>
      )}
      {state.status === "ready" &&
        state.data.rows.map((r) => (
          <div key={r.sku_id} className="day-row">
            <span className="day">
              <ProductIcon skuId={r.sku_id} size={32} />{" "}
              {productLabel(r.sku_id)}
            </span>
            {r.estimate && (
              <RangeBar range={r.estimate} max={max} unit={unitOf(r.sku_id)} />
            )}
            {r.bought_from_groups !== null && (
              <span className="small">
                {t("farmer.histBought")}: {Math.round(r.bought_from_groups)}{" "}
                {unitOf(r.sku_id)}
              </span>
            )}
          </div>
        ))}
    </details>
  );
}

export function FarmerScreen() {
  const { state, reload } = useLoad(() => api.farmers(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length)
    return (
      <div className="stack">
        <Empty />
        <FarmerHistory />
      </div>
    );
  const bySku = new Map<string, FarmerVolumeForecast[]>();
  for (const row of state.data)
    bySku.set(row.sku_id, [...(bySku.get(row.sku_id) ?? []), row]);
  const max = Math.max(1, ...state.data.map((r) => r.volume.high));
  const likely = (rows: FarmerVolumeForecast[]) =>
    rows.reduce((n, r) => n + r.volume.likely, 0);
  const ordered = [...bySku].sort((a, b) => likely(b[1]) - likely(a[1]));
  return (
    <div className="stack">
      <h2>
        <Icon name="tractor" /> {t("farmer.title")}
      </h2>
      <p className="notice">
        <Icon name="alert" /> {t("farmer.note")}
      </p>
      <p className="small">
        {t("farmer.what")} {t("farmer.threeDays")}
      </p>
      <div className="tiles-2 farmer-grid">
        {ordered.map(([sku, rows]) => (
          <section key={sku} className="card">
            <div className="total-card farmer-head">
              <ProductIcon skuId={sku} size={64} />
              <h3>{productLabel(sku)}</h3>
              <span className="badge">{t("farmer.estimate")}</span>
            </div>
            {rows.map((r) => (
              <div key={r.on} className="day-row">
                <span className="day">
                  <Icon name="calendar" size={20} /> {dayLabel(r.on)}
                </span>
                <RangeBar range={r.volume} max={max} unit={unitOf(sku)} />
              </div>
            ))}
          </section>
        ))}
      </div>
      <FarmerHistory />
    </div>
  );
}
