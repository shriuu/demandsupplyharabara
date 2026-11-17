import { LANGS, LANG_NAME, LANG_SAMPLE, setLang, useLang } from "../i18n/lang";

/** A row of script samples (not words), so it can be used without reading English. Saved on the device. */
/** `clearOfAsk`: leave room for the floating Ask button that sits at the top right for store and area managers. */
export function LanguageSwitch({ clearOfAsk = false }: { clearOfAsk?: boolean }) {
  const lang = useLang();
  return (
    <div className={`lang-switch ${clearOfAsk ? "lang-clear-ask" : ""}`} role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l}
          className={`lang-btn ${l === lang ? "lang-on" : ""}`}
          aria-pressed={l === lang}
          aria-label={LANG_NAME[l]}
          title={LANG_NAME[l]}
          lang={l}
          onClick={() => setLang(l)}
        >
          {LANG_SAMPLE[l]}
        </button>
      ))}
    </div>
  );
}
