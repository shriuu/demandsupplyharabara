import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { suggestions } from "../mock/fixtures";
import { WhyLine } from "./WhyLine";

const get = (id: string) => suggestions().find((s) => s.id === id)!;

describe("the why of an alert row", () => {
  it("says last sellable day for a discount, without repeating the sentence", () => {
    const s = get("s-mark-spinach");
    const last = { ...s, payload: { ...s.payload, earlier_than_last_day: false } } as typeof s;
    render(<WhyLine suggestion={last} />);
    expect(screen.getByText("Last sellable day")).toBeInTheDocument();
    expect(screen.queryByText(s.reason)).not.toBeInTheDocument();
  });

  it("says when a discount starts before the last day", () => {
    const s = get("s-mark-spinach");
    const early = { ...s, payload: { ...s.payload, earlier_than_last_day: true } } as typeof s;
    render(<WhyLine suggestion={early} />);
    expect(screen.getByText("Starts before the last day")).toBeInTheDocument();
  });
});
