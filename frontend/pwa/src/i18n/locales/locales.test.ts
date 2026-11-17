import { describe, expect, it } from "vitest";
import { en, productNames, productUnits } from "../strings";
import { locales } from ".";

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe.each(Object.entries(locales))("language %s", (lang, locale) => {
  it("translates every screen string", () => {
    const missing = Object.keys(en).filter((k) => !locale!.strings[k as keyof typeof en]);
    expect(missing, `${lang} is missing ${missing.join(", ")}`).toEqual([]);
  });

  it("has no strings English does not have", () => {
    const extra = Object.keys(locale!.strings).filter((k) => !(k in en));
    expect(extra).toEqual([]);
  });

  it("keeps the same {placeholders} as English, so no number or name is lost", () => {
    const bad = Object.entries(en).filter(([k, v]) => {
      const tr = locale!.strings[k as keyof typeof en];
      return tr !== undefined && placeholders(tr).join() !== placeholders(v).join();
    });
    expect(bad.map(([k]) => k)).toEqual([]);
  });

  it("names every product and unit", () => {
    expect(Object.keys(productNames).filter((id) => !locale!.products[id])).toEqual([]);
    expect([...new Set(Object.values(productUnits))].filter((u) => !locale!.units[u])).toEqual([]);
  });
});
