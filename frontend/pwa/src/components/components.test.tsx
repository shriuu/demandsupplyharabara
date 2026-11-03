import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCard } from "../screens/Dc";
import { Scoreboard } from "../screens/Area";
import { Crates } from "./Crates";
import { TrafficLight } from "./Status";
import { ReasonBadge } from "./ReasonBadge";
import type { PriceQuote } from "../api/types";

const quote = (over: Partial<PriceQuote>): PriceQuote => ({
  sku_id: "TOMATO",
  market: "M",
  on: "2026-11-03",
  modal_inr: 28,
  min_inr: null,
  max_inr: null,
  source: "Cited feed",
  fetched_at: "2026-11-03T10:00:00+05:30",
  status: "ok",
  ...over,
});

describe("Crates", () => {
  it("draws solid crates up to the order and lighter ones up to the high end", () => {
    const { container } = render(<Crates units={4} range={{ low: 3, likely: 4, high: 6 }} />);
    expect(container.querySelectorAll('[data-kind="full"]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-kind="maybe-in"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-kind="maybe"]')).toHaveLength(2);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("keeps the row short for big quantities", () => {
    const { container } = render(<Crates units={120} range={{ low: 100, likely: 120, high: 150 }} />);
    expect(container.querySelectorAll(".crate").length).toBeLessThanOrEqual(12);
  });
});

describe("TrafficLight", () => {
  it.each(["red", "amber", "green"] as const)("%s pairs colour with an icon and a word", (light) => {
    const { container } = render(<TrafficLight light={light} />);
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.querySelector(".light-word")?.textContent).toBeTruthy();
  });
});

describe("PriceCard", () => {
  it("shows the citation with a price", () => {
    render(<ul><PriceCard quote={quote({})} /></ul>);
    expect(screen.getByText(/Cited feed/)).toBeInTheDocument();
    expect(screen.getByText(/28/)).toBeInTheDocument();
  });

  it("never shows a number when the price is unavailable", () => {
    render(<ul><PriceCard quote={quote({ status: "unavailable", modal_inr: null })} /></ul>);
    expect(screen.getByText("Price unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/₹/)).toBeNull();
    expect(screen.getByText(/Cited feed/)).toBeInTheDocument();
  });
});

describe("Scoreboard", () => {
  const card = {
    scope: "All",
    period_start: "2026-10-01",
    period_end: "2026-10-31",
    waste_pct: 5,
    stockout_pct: 2,
    farmer_share: null,
    farmer_share_definition: null,
  };
  it("always shows waste, empty shelves and farmer share together, even when one is unknown", () => {
    render(<Scoreboard card={card} />);
    expect(screen.getByLabelText("Wasted")).toBeInTheDocument();
    expect(screen.getByLabelText("Empty shelves")).toBeInTheDocument();
    expect(screen.getByLabelText("Farmer share")).toBeInTheDocument();
    expect(screen.getByText("Not known")).toBeInTheDocument();
  });
});

describe("ReasonBadge", () => {
  it("shows the driver as a picture with an arrow and the sentence", () => {
    render(
      <ReasonBadge
        driver={{ kind: "weather", direction: "down", code: "x", detail: "" }}
        reason="Rain is coming."
      />,
    );
    expect(screen.getByText("Rain is coming.")).toBeInTheDocument();
    expect(screen.getByText("↓")).toBeInTheDocument();
  });
});
