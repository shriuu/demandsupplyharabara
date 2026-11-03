import { t, type StringKey } from "../i18n/strings";
import type { Driver } from "../api/types";
import { Icon, type IconName } from "./Icons";

const iconFor: Record<Driver["kind"], (d: Driver) => IconName> = {
  weather: (d) => (d.direction === "up" ? "sun" : "cloud-rain"),
  weekday: () => "calendar",
  festival: () => "lamp",
  stock_age: () => "clock",
  shelf_life: () => "hourglass",
  recent_sellout: () => "alert",
  price: () => "coin",
  promotion: () => "tag",
  rule: () => "rule",
};

/** Reason as a picture (driver icon + arrow) plus the one-sentence reason from the server. */
export function ReasonBadge({ driver, reason }: { driver: Driver; reason: string }) {
  const arrow = driver.direction === "up" ? "↑" : driver.direction === "down" ? "↓" : "";
  const key = `driver.${driver.kind}.${driver.direction}` as StringKey;
  return (
    <div className="reason">
      <span className="reason-icon" title={t(key)} data-driver={driver.kind}>
        <Icon name={iconFor[driver.kind](driver)} size={40} />
        {arrow && <span className="arrow" aria-hidden="true">{arrow}</span>}
        <span className="sr-only">{t(key)}</span>
      </span>
      <p className="reason-text">{reason}</p>
    </div>
  );
}
