import { LANGS, LANG_NAME, LANG_SAMPLE, setLang, useLang } from "../i18n/lang";

/** A row of script samples (not words), so it can be used without reading English. Saved on the device. */
/** `named`: write each language in its own script (sign-in page, where there is room); otherwise one letter.
 * `clearOfAsk`: leave room for the floating Ask button that sits at the top right for store and area managers. */
export function LanguageSwitch({ clearOfAsk = false, named = false }: { clearOfAsk?: boolean; named?: boolean }) {
  const lang = useLang();
  return (
    <div className={`lang-switch ${clearOfAsk ? "lang-clear-ask" : ""}`} role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l}
          className={`lang-btn ${named ? "lang-named" : ""} ${l === lang ? "lang-on" : ""}`}
          aria-pressed={l === lang}
          aria-label={LANG_NAME[l]}
          title={LANG_NAME[l]}
          lang={l}
          onClick={() => setLang(l)}
        >
          {named ? LANG_NAME[l] : LANG_SAMPLE[l]}
        </button>
      ))}
    </div>
  );
}
