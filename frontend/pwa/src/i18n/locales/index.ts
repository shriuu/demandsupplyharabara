import type { Lang } from "../lang";
import type { StringKey } from "../strings";
import { hi } from "./hi";
import { kn } from "./kn";
import { ta } from "./ta";
import { te } from "./te";

/** One language: every screen string, the product names, and the selling units (by their English name). */
export interface Locale {
  strings: Partial<Record<StringKey, string>>;
  products: Record<string, string>;
  units: Record<string, string>;
}

export const locales: Partial<Record<Lang, Locale>> = { kn, hi, ta, te };
