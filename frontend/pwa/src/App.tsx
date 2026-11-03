import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import type { Role } from "./api/types";
import { ChatPanel } from "./components/ChatPanel";
import { ChatFocus } from "./components/chatContext";
import { Icon, type IconName } from "./components/Icons";
import { AreaScreen } from "./screens/Area";
import { DcScreen } from "./screens/Dc";
import { FarmerScreen } from "./screens/Farmer";
import { StoreEvening } from "./screens/StoreEvening";
import { StoreMorning } from "./screens/StoreMorning";
import { StoreSurplus } from "./screens/StoreSurplus";
import { t, type StringKey } from "./i18n/strings";

const roles: { role: Role; icon: IconName; label: StringKey }[] = [
  { role: "store_manager", icon: "store", label: "role.store_manager" },
  { role: "area_manager", icon: "chart", label: "role.area_manager" },
  { role: "dc_lead", icon: "box", label: "role.dc_lead" },
  { role: "farmer_coordinator", icon: "tractor", label: "role.farmer_coordinator" },
];

type StoreTab = "evening" | "morning" | "surplus";
const storeTabs: { tab: StoreTab; icon: IconName; label: StringKey }[] = [
  { tab: "evening", icon: "moon", label: "tab.evening" },
  { tab: "morning", icon: "sun", label: "tab.morning" },
  { tab: "surplus", icon: "bag", label: "tab.surplus" },
];

/** Demo store for the store-manager screens until sign-in assigns one (sign-in is deferred). */
const DEMO_STORE_ID = "S01";

function roleFromHash(): Role | null {
  const name = window.location.hash.replace(/^#\/?/, "");
  return roles.find((r) => r.role === name)?.role ?? null;
}

export function App() {
  const [role, setRole] = useState<Role | null>(roleFromHash);
  const [tab, setTab] = useState<StoreTab>("evening");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [killed, setKilled] = useState(false);

  useEffect(() => {
    const onHash = () => setRole(roleFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    api.health().then((h) => setKilled(h.kill_switch), () => undefined);
  }, []);

  const choose = (next: Role | null) => {
    window.location.hash = next ? `/${next}` : "";
    setRole(next);
  };
  const setFocus = useCallback((id: string | null) => setFocusId(id), []);

  return (
    <ChatFocus.Provider value={setFocus}>
      <header className="topbar">
        {role ? (
          <button className="btn btn-plain" onClick={() => choose(null)} aria-label={t("role.switch")}>
            <Icon name="back" size={32} />
            <Icon name={roles.find((r) => r.role === role)?.icon ?? "home"} size={32} />
            <span>{t(`role.${role}`)}</span>
          </button>
        ) : (
          <span className="brand">
            <Icon name="home" /> {t("app.name")}
          </span>
        )}
      </header>
      {killed && (
        <p className="notice notice-error" role="status">
          <Icon name="stop" /> {t("app.killed")}
        </p>
      )}
      <main>
        {!role && (
          <nav className="role-grid" aria-label={t("role.pick")}>
            {roles.map((r) => (
              <button key={r.role} className="btn role-tile" onClick={() => choose(r.role)}>
                <Icon name={r.icon} size={64} />
                <span>{t(r.label)}</span>
              </button>
            ))}
          </nav>
        )}
        {role === "store_manager" && (
          <>
            <nav className="tabs" aria-label={t("role.store_manager")}>
              {storeTabs.map((s) => (
                <button
                  key={s.tab}
                  className={`btn tab ${tab === s.tab ? "tab-on" : ""}`}
                  aria-pressed={tab === s.tab}
                  onClick={() => setTab(s.tab)}
                >
                  <Icon name={s.icon} size={36} />
                  <span>{t(s.label)}</span>
                </button>
              ))}
            </nav>
            {tab === "evening" && <StoreEvening storeId={DEMO_STORE_ID} />}
            {tab === "morning" && <StoreMorning storeId={DEMO_STORE_ID} />}
            {tab === "surplus" && <StoreSurplus storeId={DEMO_STORE_ID} />}
          </>
        )}
        {role === "area_manager" && <AreaScreen onKilled={() => setKilled(true)} />}
        {role === "dc_lead" && <DcScreen />}
        {role === "farmer_coordinator" && <FarmerScreen />}
      </main>
      {role && <ChatPanel role={role} focusId={focusId} />}
    </ChatFocus.Provider>
  );
}
