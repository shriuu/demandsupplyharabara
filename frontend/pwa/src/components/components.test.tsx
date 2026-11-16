import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCard } from "../screens/Dc";
import { Measure } from "./Measure";
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
    const { container } = render(<Crates units={4} range={{ low: 3, likely: 4, high: 6 }} skuId="P01" />);
    expect(container.querySelectorAll('[data-kind="full"]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-kind="maybe-in"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-kind="maybe"]')).toHaveLength(2);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("keeps the row short for big quantities", () => {
    const { container } = render(<Crates units={120} range={{ low: 100, likely: 120, high: 150 }} skuId="P01" />);
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

describe("Measure", () => {
  it("shows the number, the target and how this compares, in a word as well as a bar", () => {
    render(<Measure label="score.waste" icon="bag" value={8.1} target={5.5} allStores={7.7} />);
    expect(screen.getByText("8.1%")).toBeInTheDocument();
    expect(screen.getByText("Above target")).toBeInTheDocument();
    expect(screen.getByText("Target 5.5%")).toBeInTheDocument();
    expect(screen.getByText("All stores 7.7%")).toBeInTheDocument();
  });

  it("says on target when it is, and near target between the target and today's level", () => {
    const { rerender } = render(<Measure label="score.stockout" icon="box" value={6} target={7} nearLimit={9.1} />);
    expect(screen.getByText("On target")).toBeInTheDocument();
    rerender(<Measure label="score.stockout" icon="box" value={8} target={7} nearLimit={9.1} />);
    expect(screen.getByText("Near target")).toBeInTheDocument();
    rerender(<Measure label="score.stockout" icon="box" value={12} target={7} nearLimit={9.1} />);
    expect(screen.getByText("Above target")).toBeInTheDocument();
  });

  it("never shows zero for an unknown value", () => {
    render(<Measure label="score.waste" icon="bag" value={null} target={5.5} />);
    expect(screen.getByText("No counts yet")).toBeInTheDocument();
    expect(screen.queryByText("0%")).toBeNull();
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
