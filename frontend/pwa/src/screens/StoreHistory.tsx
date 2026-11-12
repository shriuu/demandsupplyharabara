import { useState } from "react";
import { CalendarPick, addDays, todayIso } from "../components/CalendarPick";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { DayHistory } from "../api/types";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Loading, LoadError } from "../components/Status";
import { productName, t, unitOf } from "../i18n/strings";

export const pct = (v: number | null) =>
  v === null ? "-" : `${Math.round(v)}%`;

export function DayCard({
  day,
  defaultOpen = false,
}: {
  day: DayHistory;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const closed = day.products_closed > 0;
  const date = new Date(`${day.on}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  return (
    <li className="card">
      <button
        className="btn btn-plain decided-row"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        style={{ width: "100%" }}
      >
        <strong>{date}</strong>
        <span>
          {day.orders_made
            ? t("hist.orders", {
                ok: day.orders_approved,
                edit: day.orders_edited,
                no: day.orders_rejected,
                late: day.orders_expired,
              })
            : t("hist.noOrders")}
        </span>
      </button>
      <p className="small">
        <Icon name={closed ? "tick" : "clock"} size={18} />{" "}
        {closed
          ? t("hist.closed", {
              waste: pct(day.waste_pct),
              out: pct(day.stockout_pct),
            })
          : t("hist.notClosed")}
      </p>
      {open && (
        <>
          <ul className="plain-list">
            {day.orders.map((o) => (
              <li key={`o-${o.sku_id}`} className="decided-row">
                <span>
                  <ProductIcon skuId={o.sku_id} size={32} />{" "}
                  {productName(o.sku_id)}
                </span>
                <span>
                  {o.final_units !== null
                    ? t("hist.ordered", {
                        n: Math.round(o.final_units),
                        unit: unitOf(o.sku_id),
                      })
                    : t(`hist.state.${o.state}` as never)}{" "}
                  <span className="small">
                    ({t("hist.suggested", { s: Math.round(o.suggested_units) })}
                    )
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <ul className="plain-list">
            {day.closing.map((c) => (
              <li key={`c-${c.sku_id}`} className="decided-row">
                <span>{productName(c.sku_id)}</span>
                <span>
                  {t("hist.soldWasted", {
                    sold: Math.round(c.units_sold),
                    wasted: Math.round(c.units_wasted),
                  })}
                  {c.sold_out ? ` · ${t("hist.ranOut")}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </li>
  );
}

/** The store manager's history: pick any past day on the calendar. Starts on yesterday. */
export function StoreHistory() {
  const [day, setDay] = useState(() => addDays(todayIso(), -1));
  const [bounds, setBounds] = useState<{ first: string; last: string } | null>(
    null,
  );
  const { state, reload } = useLoad(async () => {
    const view = await api.dayHistory(day);
    setBounds({ first: view.first_day, last: view.last_day });
    return view;
  }, day);
  return (
    <div className="stack">
      <h2>
        <Icon name="calendar" /> {t("hist.title")}
      </h2>
      <p className="small">{t("hist.note")}</p>
      <CalendarPick
        value={day}
        min={bounds?.first ?? day}
        max={bounds?.last ?? day}
        onChange={setDay}
      />
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <LoadError onRetry={reload} />}
      {state.status === "ready" && (
        <ul className="stack">
          <DayCard key={state.data.on} day={state.data.day} defaultOpen />
        </ul>
      )}
    </div>
  );
}
