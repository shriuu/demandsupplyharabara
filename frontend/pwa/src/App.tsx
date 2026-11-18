import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { loadSession, setOnExpired, setOnSwitchedOff } from "./api/session";
import type { LoginResponse, Role } from "./api/types";
import { ChatPanel } from "./components/ChatPanel";
import { ChatFocus } from "./components/chatContext";
import { Icon, type IconName } from "./components/Icons";
import { LanguageSwitch } from "./components/LanguageSwitch";
import { useLang } from "./i18n/lang";
import { AreaScreen } from "./screens/Area";
import { DcScreen } from "./screens/Dc";
import { FarmerScreen } from "./screens/Farmer";
import { Login } from "./screens/Login";
import { StoreClosing } from "./screens/StoreClosing";
import { StoreEvening } from "./screens/StoreEvening";
import { MyNumbers } from "./screens/MyNumbers";
import { StoreMorning } from "./screens/StoreMorning";
import { StoreSurplus } from "./screens/StoreSurplus";
import { storeLabel, t, type StringKey } from "./i18n/strings";

const roleIcons: Record<Role, IconName> = {
  store_manager: "store",
  area_manager: "chart",
  dc_lead: "box",
  farmer_coordinator: "tractor",
};

type StoreTab = "evening" | "morning" | "closing" | "numbers";
const storeTabs: { tab: StoreTab; icon: IconName; label: StringKey; tip: StringKey }[] = [
  { tab: "evening", icon: "moon", label: "tab.evening", tip: "tip.evening" },
  { tab: "morning", icon: "sun", label: "tab.morning", tip: "tip.morning" },
  { tab: "closing", icon: "tick", label: "tab.closing", tip: "tip.closing" },
  { tab: "numbers", icon: "chart", label: "tab.numbers", tip: "tip.numbers" },
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
  const lang = useLang(); // a new language rebuilds the screens; the sign-in is kept here
  const role = session?.role ?? null;
  const storeId = session?.store_id ?? null;

  return (
    <ChatFocus.Provider key={lang} value={setFocus}>
      <header className="topbar">
        {role ? (
          <div className="topbar-row">
            <span className="brand">
              <Icon name={roleIcons[role]} size={32} />
              <span className="brand-text">
                <span>{t(`role.${role}`)}</span>
                {role === "store_manager" && storeId ? (
                  <small data-testid="brand-place">{storeLabel(storeId)}</small>
                ) : session?.area_name ? (
                  <small data-testid="brand-place">{session.area_name}</small>
                ) : null}
              </span>
            </span>
            <LanguageSwitch clearOfAsk={role === "store_manager" || role === "area_manager"} />
            <button className="btn btn-plain" onClick={signOut} aria-label={t("app.logout")} data-tip={t("tip.logout")}>
              <Icon name="logout" size={32} />
            </button>
          </div>
        ) : (
          <div className="topbar-row">
            <span className="brand">
              <Icon name="home" /> {t("app.name")}
            </span>
            <LanguageSwitch named />
          </div>
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
                  data-tip={t(s.tip)}
                  onClick={() => setTab(s.tab)}
                >
                  <Icon name={s.icon} size={36} />
                  <span>{t(s.label)}</span>
                </button>
              ))}
            </nav>
            {tab === "evening" && <StoreEvening storeId={storeId} />}
            {tab === "morning" && (
              <div className="stack">
                <h2>
                  <Icon name="sun" /> {t("morning.alerts")}
                </h2>
                <StoreMorning storeId={storeId} />
                <h2>
                  <Icon name="bag" /> {t("morning.surplus")}
                </h2>
                <StoreSurplus storeId={storeId} />
              </div>
            )}
            {tab === "closing" && <StoreClosing storeId={storeId} />}
            {tab === "numbers" && <MyNumbers />}
          </>
        )}
        {role === "area_manager" && <AreaScreen killed={killed} onKilledChange={setKilled} />}
        {role === "dc_lead" && <DcScreen />}
        {role === "farmer_coordinator" && <FarmerScreen />}
      </main>
      {/* Ask explains stored suggestions; the DC lead and farmer coordinator have none, so no button */}
      {(role === "store_manager" || role === "area_manager") && <ChatPanel role={role} focusId={focusId} />}
    </ChatFocus.Provider>
  );
}
