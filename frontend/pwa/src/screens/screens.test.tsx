import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import { installMockFetch } from "../mock/handlers";

let mock: ReturnType<typeof installMockFetch>;
beforeEach(() => {
  mock = installMockFetch();
  window.location.hash = "";
});

async function openRole(name: string) {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name }));
  return user;
}

describe("store manager evening", () => {
  it("accepting sends an approve and moves to the next product", async () => {
    const user = await openRole("Store manager");
    expect(await screen.findByRole("heading", { name: "Tomato" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("heading", { name: "Banana" })).toBeInTheDocument();
    expect(mock.decisions[0]).toMatchObject({ action: "approve", suggestion_id: "s-order-tomato" });
  });

  it("an edit needs a reason before it can be saved", async () => {
    const user = await openRole("Store manager");
    await screen.findByRole("heading", { name: "Tomato" });
    await user.click(screen.getByRole("button", { name: "Less" }));
    const save = screen.getByRole("button", { name: "Save change" });
    expect(save).toBeDisabled();
    await user.type(screen.getByPlaceholderText("Write a reason to save"), "Market is slow");
    expect(save).toBeEnabled();
    await user.click(save);
    await waitFor(() => expect(mock.decisions).toHaveLength(1));
    expect(mock.decisions[0]).toMatchObject({ action: "edit", edited_units: 7, reason: "Market is slow" });
  });

  it("a big edit asks are-you-sure first", async () => {
    const user = await openRole("Store manager");
    await screen.findByRole("heading", { name: "Tomato" });
    for (let i = 0; i < 4; i++) await user.click(screen.getByRole("button", { name: "Less" }));
    await user.type(screen.getByPlaceholderText("Write a reason to save"), "Closing early");
    await user.click(screen.getByRole("button", { name: "Save change" }));
    expect(mock.decisions).toHaveLength(0);
    await user.click(await screen.findByRole("button", { name: "Yes" }));
    await waitFor(() => expect(mock.decisions[0]).toMatchObject({ action: "edit", edited_units: 4 }));
  });

  it("rejecting asks first", async () => {
    const user = await openRole("Store manager");
    await screen.findByRole("heading", { name: "Tomato" });
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(mock.decisions).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(mock.decisions[0]).toMatchObject({ action: "reject" }));
  });
});

describe("area manager", () => {
  it("shows the scoreboard with all three measures beside the queue", async () => {
    await openRole("Area manager");
    expect(await screen.findByLabelText("Wasted")).toBeInTheDocument();
    expect(screen.getByLabelText("Empty shelves")).toBeInTheDocument();
    expect(screen.getByLabelText("Farmer share")).toBeInTheDocument();
  });

  it("the kill switch needs a second step", async () => {
    const user = await openRole("Area manager");
    await user.click(await screen.findByRole("button", { name: /Stop all suggestions/ }));
    expect((await (await fetch("/api/v1/health")).json()).kill_switch).toBe(false);
    await user.click(screen.getByRole("button", { name: "Yes" }));
    expect(await screen.findByText("Suggestions are stopped")).toBeInTheDocument();
    expect((await (await fetch("/api/v1/health")).json()).kill_switch).toBe(true);
  });
});

describe("dc lead", () => {
  it("shows unavailable prices without a number and keeps trimming as a suggestion only", async () => {
    await openRole("DC buying lead");
    expect(await screen.findByText("Price unavailable")).toBeInTheDocument();
    expect(screen.getByText("Buy less on the spot market")).toBeInTheDocument();
    expect(screen.getAllByText(/Mock price feed/).length).toBeGreaterThan(0);
  });
});

describe("farmer coordinator", () => {
  it("labels every product's volumes as an estimate", async () => {
    await openRole("Farmer group");
    expect(await screen.findAllByText("Estimate")).toHaveLength(2);
  });
});

describe("chat panel", () => {
  it("answers from the suggestion, or says it does not have it", async () => {
    const user = await openRole("Store manager");
    await screen.findByRole("heading", { name: "Tomato" });
    await user.click(screen.getByRole("button", { name: "Ask" }));
    const box = screen.getByPlaceholderText("Type your question");
    await user.type(box, "why?{Enter}");
    expect(await screen.findAllByText("Rain is coming tomorrow, so fewer shoppers will visit.")).not.toHaveLength(0);
    await user.type(box, "what is the capital?{Enter}");
    expect(await screen.findByText("I don't have that.")).toBeInTheDocument();
    expect(mock.asked[0].suggestion_id).toBe("s-order-tomato");
  });
});
