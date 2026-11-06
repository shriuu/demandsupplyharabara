import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { FarmerVolumeForecast } from "../api/types";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { RangeBar } from "../components/RangeBar";
import { Empty, Loading, LoadError } from "../components/Status";
import { productLabel, t, unitOf } from "../i18n/strings";

function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

export function FarmerScreen() {
  const { state, reload } = useLoad(() => api.farmers(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const bySku = new Map<string, FarmerVolumeForecast[]>();
  for (const row of state.data) bySku.set(row.sku_id, [...(bySku.get(row.sku_id) ?? []), row]);
  const max = Math.max(1, ...state.data.map((r) => r.volume.high));
  const likely = (rows: FarmerVolumeForecast[]) => rows.reduce((n, r) => n + r.volume.likely, 0);
  const ordered = [...bySku].sort((a, b) => likely(b[1]) - likely(a[1]));
  return (
    <div className="stack">
      <h2>
        <Icon name="tractor" /> {t("farmer.title")}
      </h2>
      <p className="notice">
        <Icon name="alert" /> {t("farmer.note")}
      </p>
      <p className="small">{t("farmer.what")}</p>
      <div className="tiles-2">
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
    </div>
  );
}
