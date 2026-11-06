import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { OrderPayload, Suggestion } from "../api/types";
import { Counter } from "../components/Counter";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Loading, LoadError } from "../components/Status";
import { todayIso } from "../dates";
import { productName, t, unitOf } from "../i18n/strings";
import { biggestFirst } from "./priority";

/** The store records how the day went for each product it ordered. A record only. */
export function StoreClosing({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    async () => {
      const [approved, edited] = await Promise.all([
        api.suggestions({ role: "store_manager", store_id: storeId, kind: "order", state: "approved" }),
        api.suggestions({ role: "store_manager", store_id: storeId, kind: "order", state: "edited" }),
      ]);
      return [...approved, ...edited];
    },
    [storeId],
  );
  const [openId, setOpenId] = useState<string | null>(null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const queue = [...state.data].sort(biggestFirst);
  if (!queue.length) return <p className="notice" role="status">{t("closing.none")}</p>;
  const open = queue.find((s) => s.id === openId);
  if (open) {
    return (
      <>
        <button className="btn btn-plain" onClick={() => setOpenId(null)}>
          <Icon name="back" size={28} /> {t("order.back")}
        </button>
        <ClosingCard
          key={open.id}
          suggestion={open}
          storeId={storeId}
          onDone={() => {
            setOpenId(null);
            reload();
          }}
        />
      </>
    );
  }
  return (
    <>
      <p className="small">{t("closing.tap")}</p>
      <ul className="tiles">
        {queue.map((s) => (
          <li key={s.id}>
            <button className="btn tile" style={{ width: "100%" }} onClick={() => setOpenId(s.id)}>
              <ProductIcon skuId={s.sku_id} size={72} />
              <span className="tile-name">{productName(s.sku_id)}</span>
              <span className="tile-amount">{t("order.units", { n: Math.round((s.payload as OrderPayload).recommended_units), unit: unitOf(s.sku_id) })}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function ClosingCard({ suggestion, storeId, onDone }: { suggestion: Suggestion; storeId: string; onDone: () => void }) {
  const [sold, setSold] = useState(0);
  const [wasted, setWasted] = useState(0);
  const [ranOut, setRanOut] = useState(false);
  const [failed, setFailed] = useState(false);
  const unit = unitOf(suggestion.sku_id);

  async function save() {
    setFailed(false);
    try {
      await api.recordOutcome({
        kind: "closing",
        on: todayIso(),
        store_id: storeId,
        sku_id: suggestion.sku_id,
        units_sold: sold,
        units_wasted: wasted,
        sold_out: ranOut,
        suggestion_id: suggestion.id,
      });
      onDone();
    } catch {
      setFailed(true);
    }
  }

  return (
    <article className="card order-card">
      <div className="product">
        <ProductIcon skuId={suggestion.sku_id} size={112} />
        <h2>{productName(suggestion.sku_id)}</h2>
      </div>
      <Counter label={t("closing.sold")} value={sold} step={1} unit={unit} onChange={setSold} />
      <Counter label={t("closing.wasted")} value={wasted} step={1} unit={unit} onChange={setWasted} />
      <p className="counter-label">{t("closing.ranOut")}</p>
      <div className="tickcross">
        <button className={`btn btn-yes ${ranOut ? "" : "btn-dim"}`} aria-pressed={ranOut} onClick={() => setRanOut(true)}>
          <Icon name="tick" size={36} /> {t("closing.yes")}
        </button>
        <button className={`btn btn-no ${ranOut ? "btn-dim" : ""}`} aria-pressed={!ranOut} onClick={() => setRanOut(false)}>
          <Icon name="cross" size={36} /> {t("closing.no")}
        </button>
      </div>
      <p className="small">{t("closing.note")}</p>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <button className="btn btn-yes" style={{ width: "100%" }} onClick={() => void save()}>
        <Icon name="tick" size={40} /> {t("closing.save")}
      </button>
    </article>
  );
}
