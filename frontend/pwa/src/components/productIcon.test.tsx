import { describe, expect, it } from "vitest";
import { productNames } from "../i18n/strings";
import { looks } from "./ProductIcon";

describe("product pictures", () => {
  it("has its own picture for every product, so none falls back to the grey circle", () => {
    const missing = Object.keys(productNames).filter((id) => !looks[id]);
    expect(missing).toEqual([]);
  });
});
