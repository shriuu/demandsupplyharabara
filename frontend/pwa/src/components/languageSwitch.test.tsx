import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "../App";
import { setLang } from "../i18n/lang";
import { productName, t, unitOf } from "../i18n/strings";

afterEach(() => setLang("en"));

describe("language switch", () => {
  it("changes the words, product names and units, and falls back to English for nothing", () => {
    setLang("kn");
    expect(t("login.title")).toBe("ನಿಮ್ಮ ಪಿನ್ ನಮೂದಿಸಿ");
    expect(productName("P01")).toBe("ಟೊಮೆಟೊ");
    expect(unitOf("P04")).toBe("ಡಜನ್");
    setLang("en");
    expect(t("login.title")).toBe("Enter your PIN");
  });

  it("is a row of script samples on the sign-in page, and the page changes when one is tapped", async () => {
    const user = userEvent.setup();
    render(<App />);
    const group = await screen.findByRole("group", { name: "Language" });
    expect(group.querySelectorAll("button")).toHaveLength(5);
    await user.click(screen.getByRole("button", { name: "हिन्दी" }));
    expect(await screen.findByText("अपना पिन डालें")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("hi");
  });
});
