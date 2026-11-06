import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { loadSession, setOnExpired, setOnSwitchedOff } from "./api/session";
import type { LoginResponse, Role } from "./api/types";
import { ChatPanel } from "./components/ChatPanel";
import { ChatFocus } from "./components/chatContext";
import { Icon, type IconName } from "./components/Icons";
import { AreaScreen } from "./screens/Area";
import { DcScreen } from "./screens/Dc";
import { FarmerScreen } from "./screens/Farmer";
import { Login } from "./screens/Login";
import { StoreClosing } from "./screens/StoreClosing";
import { StoreEvening } from "./screens/StoreEvening";
import { StoreMorning } from "./screens/StoreMorning";
import { StoreSurplus } from "./screens/StoreSurplus";
import { t, type StringKey } from "./i18n/strings";

const roleIcons: Record<Role, IconName> = {
  store_manager: "store",
  area_manager: "chart",
  dc_lead: "box",
  farmer_coordinator: "tractor",
};

type StoreTab = "evening" | "morning" | "surplus" | "closing";
const storeTabs: { tab: StoreTab; icon: IconName; label: StringKey }[] = [
  { tab: "evening", icon: "moon", label: "tab.evening" },
  { tab: "morning", icon: "sun", label: "tab.morning" },
  { tab: "surplus", icon: "bag", label: "tab.surplus" },
  { tab: "closing", icon: "tick", label: "tab.closing" },
];

export function App() {
  const [session, setSession] = useState<LoginResponse | null>(loadSession);
  const [expired, setExpired] = useState(false);
  const [tab, setTab] = useState<StoreTab>("evening");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [killed, setKilled] = useState(false);

  useEffect(() => {
    setOnExpired(() => {
      setSession(null);
      setExpired(true);
    });
    setOnSwitchedOff(() => setKilled(true));
  }, []);
  useEffect(() => {
    api.health().then((h) => setKilled(h.kill_switch), () => undefined);
  }, [session]);

  const signOut = () => {
    api.logout();
    setSession(null);
    setExpired(false);
  };
  const setFocus = useCallback((id: string | null) => setFocusId(id), []);
  const role = session?.role ?? null;
  const storeId = session?.store_id ?? null;

  return (
    <ChatFocus.Provider value={setFocus}>
      <header className="topbar">
        {role ? (
          <div className="topbar-row">
            <span className="brand">
              <Icon name={roleIcons[role]} size={32} /> {t(`role.${role}`)}
              {session?.area_name ? ` · ${session.area_name}` : ""}
            </span>
            <button className="btn btn-plain" onClick={signOut} aria-label={t("app.logout")}>
              <Icon name="logout" size={32} />
            </button>
          </div>
        ) : (
          <span className="brand">
            <Icon name="home" /> {t("app.name")}
          </span>
        )}
      </header>
      {role && <p className="notice job">{t(`job.${role}`)}</p>}
      {killed && (
        <p className="notice notice-error" role="status">
          <Icon name="stop" /> {t("app.killed")}
        </p>
      )}
      <main>
        {!session && <Login onSignedIn={(s) => { setExpired(false); setSession(s); }} notice={expired ? "login.expired" : undefined} />}
        {role === "store_manager" && storeId && (
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
            {tab === "evening" && <StoreEvening storeId={storeId} />}
            {tab === "morning" && <StoreMorning storeId={storeId} />}
            {tab === "surplus" && <StoreSurplus storeId={storeId} />}
            {tab === "closing" && <StoreClosing storeId={storeId} />}
          </>
        )}
        {role === "area_manager" && <AreaScreen killed={killed} onKilledChange={setKilled} />}
        {role === "dc_lead" && <DcScreen />}
        {role === "farmer_coordinator" && <FarmerScreen />}
      </main>
      {role && <ChatPanel role={role} focusId={focusId} />}
    </ChatFocus.Provider>
  );
}
