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

/** One row per product: what was ordered, sold, thrown away and left. Labels are said once, on top. */
function DayTable({ day }: { day: DayHistory }) {
  const skus = [
    ...new Set([...day.orders.map((o) => o.sku_id), ...day.closing.map((c) => c.sku_id)]),
  ];
  const order = (sku: string) => day.orders.find((o) => o.sku_id === sku);
  const close = (sku: string) => day.closing.find((c) => c.sku_id === sku);
  const dash = <span className="small">–</span>;
  return (
    <table className="day-table" data-testid="day-table">
      <thead>
        <tr>
          <th scope="col">{t("hist.col.product")}</th>
          <th scope="col">{t("hist.col.ordered")}</th>
          <th scope="col">{t("hist.col.sold")}</th>
          <th scope="col">{t("hist.col.thrown")}</th>
          <th scope="col">{t("hist.col.left")}</th>
        </tr>
      </thead>
      <tbody>
        {skus.map((sku) => {
          const o = order(sku);
          const c = close(sku);
          const changed = o && o.final_units !== null && Math.round(o.final_units) !== Math.round(o.suggested_units);
          return (
            <tr key={sku} className={c?.sold_out ? "day-out" : undefined}>
              <th scope="row">
                <ProductIcon skuId={sku} size={28} /> {productName(sku)}{" "}
                <span className="small">{unitOf(sku)}</span>
              </th>
              <td>
                {!o ? (
                  dash
                ) : o.final_units !== null ? (
                  <>
                    <strong>{Math.round(o.final_units)}</strong>
                    {changed && <span className="small"> {t("hist.suggested", { s: Math.round(o.suggested_units) })}</span>}
                  </>
                ) : (
                  <>
                    {t(`hist.state.${o.state}` as never)}
                    <span className="small"> {t("hist.suggested", { s: Math.round(o.suggested_units) })}</span>
                  </>
                )}
              </td>
              <td>{c ? Math.round(c.units_sold) : dash}</td>
              <td className={c && c.units_wasted > 0 ? "day-thrown" : undefined}>{c ? Math.round(c.units_wasted) : dash}</td>
              <td>
                {c && c.sold_out ? (
                  <span className="day-ranout">
                    <Icon name="alert" size={16} /> {t("hist.ranOut")}
                  </span>
                ) : c && c.units_left != null ? (
                  Math.round(c.units_left)
                ) : (
                  dash
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

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
      {open && <DayTable day={day} />}
    </li>
  );
}

/**
 * Pick any past day on the calendar. Starts on yesterday. A store manager sees their own store; an area
 * manager names a store in their area (`storeId`).
 */
export function StoreHistory({ storeId }: { storeId?: string }) {
  const [day, setDay] = useState(() => addDays(todayIso(), -1));
  const [bounds, setBounds] = useState<{ first: string; last: string } | null>(
    null,
  );
  const { state, reload } = useLoad(async () => {
    const view = await api.dayHistory(day, storeId);
    setBounds({ first: view.first_day, last: view.last_day });
    return view;
  }, `${storeId ?? ""}:${day}`);
  return (
    <div className="stack">
      <h2>
        <Icon name="calendar" /> {t("hist.title")}
      </h2>
      <p className="small">{t(storeId ? "hist.noteStore" : "hist.note")}</p>
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
