import { t } from "../i18n/strings";
import { Icon } from "./Icons";

/** Big green tick and big red cross: same place on every screen. */
export function TickCross({
  onTick,
  onCross,
  tickLabel = t("action.accept"),
  disabled = false,
}: {
  onTick: () => void;
  onCross: () => void;
  tickLabel?: string;
  disabled?: boolean;
}) {
  return (
    <div className="tickcross">
      <button className="btn btn-no" onClick={onCross} disabled={disabled} aria-label={t("action.reject")}>
        <Icon name="cross" size={48} />
      </button>
      <button className="btn btn-yes" onClick={onTick} disabled={disabled} aria-label={tickLabel}>
        <Icon name="tick" size={48} />
      </button>
    </div>
  );
}

/** A picture-first "are you sure" step. Nothing important happens on one accidental tap. */
export function Confirm({
  message,
  onYes,
  onNo,
}: {
  message: string;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal" role="alertdialog" aria-modal="true" aria-label={t("action.confirm.sure")}>
        <Icon name="alert" size={64} />
        <p className="modal-text">{message}</p>
        <div className="tickcross">
          <button className="btn btn-no" onClick={onNo} aria-label={t("action.confirm.no")}>
            <Icon name="back" size={48} />
          </button>
          <button className="btn btn-yes" onClick={onYes} aria-label={t("action.confirm.yes")}>
            <Icon name="tick" size={48} />
          </button>
        </div>
      </div>
    </div>
  );
}
