import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { FarmerVolumeForecast } from "../api/types";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { RangeBar } from "../components/RangeBar";
import { Empty, Loading, LoadError } from "../components/Status";
import { productLabel, t } from "../i18n/strings";

export function FarmerScreen() {
  const { state, reload } = useLoad(() => api.farmers(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const bySku = new Map<string, FarmerVolumeForecast[]>();
  for (const row of state.data) bySku.set(row.sku_id, [...(bySku.get(row.sku_id) ?? []), row]);
  const max = Math.max(1, ...state.data.map((r) => r.volume.high));
  return (
    <div className="stack">
      <h2>
        <Icon name="tractor" /> {t("farmer.title")}
      </h2>
      <p className="notice">
        <Icon name="alert" /> {t("farmer.note")}
      </p>
      {[...bySku].map(([sku, rows]) => (
        <section key={sku} className="card">
          <div className="total-card">
            <ProductIcon skuId={sku} size={64} />
            <h3>{productLabel(sku)}</h3>
            <span className="badge">{t("farmer.estimate")}</span>
          </div>
          {rows.map((r) => (
            <div key={r.on} className="day-row">
              <span className="day">
                <Icon name="calendar" size={20} /> {r.on}
              </span>
              <RangeBar range={r.volume} max={max} />
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
