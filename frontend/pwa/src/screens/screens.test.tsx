import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import { clearSession, signalExpired } from "../api/session";
import { installMockFetch } from "../mock/handlers";

const PIN_FOR: Record<string, string> = {
  "Store manager": "1111",
  "Area manager": "3333",
  "DC buying lead": "4444",
  "Farmer group": "5555",
};

let mock: ReturnType<typeof installMockFetch>;
beforeEach(() => {
  mock = installMockFetch();
  clearSession();
});

async function enterPin(user: ReturnType<typeof userEvent.setup>, pin: string) {
  for (const digit of pin) await user.click(await screen.findByRole("button", { name: digit }));
  await user.click(screen.getByRole("button", { name: "Go" }));
}

async function openProduct(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  return screen.findByRole("heading", { name });
}

async function openRole(name: string) {
  const user = userEvent.setup();
  render(<App />);
  await enterPin(user, PIN_FOR[name]);
  return user;
}

describe("sign-in", () => {
  it("a wrong PIN shows a message and stays on the pad", async () => {
    const user = userEvent.setup();
    render(<App />);
    await enterPin(user, "9999");
    expect(await screen.findByText("Wrong PIN. Try again.")).toBeInTheDocument();
  });

  it("too many wrong PINs shows the wait message", async () => {
    const user = userEvent.setup();
    render(<App />);
    for (let i = 0; i < 5; i++) await enterPin(user, "9999");
    await enterPin(user, "1111");
    expect(await screen.findByText("Too many tries. Wait a minute.")).toBeInTheDocument();
  });

  it("goes to the screen for the role the server returns, and sends the token", async () => {
    await openRole("DC buying lead");
    expect(await screen.findByText("Totals to buy")).toBeInTheDocument();
  });

  it("an ended sign-in goes back to the PIN pad", async () => {
    await openRole("Farmer group");
    await screen.findAllByText("Estimate");
    act(() => signalExpired());
    expect(await screen.findByText("Please sign in again.")).toBeInTheDocument();
  });
  it("draws six dots before anything is typed", async () => {
    const { container } = render(<App />);
    await screen.findByRole("button", { name: "1" });
    expect(container.querySelectorAll(".pin-dots .dot")).toHaveLength(6);
    expect(container.querySelectorAll(".pin-dots .dot-on")).toHaveLength(0);
  });

  it("fills the dots as digits are pressed and stops at the longest PIN", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    for (const digit of "123456") await user.click(await screen.findByRole("button", { name: digit }));
    expect(container.querySelectorAll(".pin-dots .dot-on")).toHaveLength(6);
    for (const digit of "7890") await user.click(screen.getByRole("button", { name: digit }));
    expect(container.querySelectorAll(".pin-dots .dot")).toHaveLength(8);
    expect(container.querySelectorAll(".pin-dots .dot-on")).toHaveLength(8);
  });

});

describe("store manager evening", () => {
  it("shows the products as tiles, biggest sellers first", async () => {
    await openRole("Store manager");
    const tiles = await screen.findAllByRole("button", { name: /crates/ });
    expect(tiles[0]).toHaveTextContent("Banana");
    expect(tiles[1]).toHaveTextContent("Tomato");
  });

  it("accepting sends an approve and goes back to the tiles", async () => {
    const user = await openRole("Store manager");
    expect(await openProduct(user, "Tomato")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("button", { name: /Banana/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tomato/ })).not.toBeInTheDocument();
    expect(mock.decisions[0]).toMatchObject({ action: "approve", suggestion_id: "s-order-tomato" });
  });

  it("an edit needs a reason before it can be saved", async () => {
    const user = await openRole("Store manager");
    await openProduct(user, "Tomato");
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
    await openProduct(user, "Tomato");
    for (let i = 0; i < 4; i++) await user.click(screen.getByRole("button", { name: "Less" }));
    await user.type(screen.getByPlaceholderText("Write a reason to save"), "Closing early");
    await user.click(screen.getByRole("button", { name: "Save change" }));
    expect(mock.decisions).toHaveLength(0);
    await user.click(await screen.findByRole("button", { name: "Yes" }));
    await waitFor(() => expect(mock.decisions[0]).toMatchObject({ action: "edit", edited_units: 4 }));
  });

  it("rejecting asks first", async () => {
    const user = await openRole("Store manager");
    await openProduct(user, "Tomato");
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(mock.decisions).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(mock.decisions[0]).toMatchObject({ action: "reject" }));
  });
});

describe("store manager closing", () => {
  it("records how a decided order went, and the order leaves the list", async () => {
    const user = await openRole("Store manager");
    await openProduct(user, "Tomato");
    await user.click(screen.getByRole("button", { name: "Accept" }));
    await user.click(await screen.findByRole("button", { name: /Closing/ }));
    await openProduct(user, "Tomato");
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole("button", { name: "Sold: More" }));
    await user.click(screen.getByRole("button", { name: /Yes, it ran out/ }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mock.outcomes).toHaveLength(1));
    expect(mock.outcomes[0]).toMatchObject({
      kind: "closing",
      store_id: "S01",
      units_sold: 3,
      units_wasted: 0,
      sold_out: true,
      suggestion_id: "s-order-tomato",
    });
    expect(await screen.findByText("No approved orders to close yet.")).toBeInTheDocument();
  });
});

describe("area manager", () => {
  it("shows the scoreboard with all three measures beside the queue", async () => {
    await openRole("Area manager");
    expect(await screen.findByLabelText("Wasted")).toBeInTheDocument();
    expect(screen.getByLabelText("Empty shelves")).toBeInTheDocument();
    expect(screen.getByLabelText("Farmer share")).toBeInTheDocument();
  });

  it("says when nothing has been recorded yet, instead of showing zeros", async () => {
    await openRole("Area manager");
    expect(await screen.findByText("Nothing recorded for this yet.")).toBeInTheDocument();
  });

  it("the kill switch needs a second step, and can be switched off again", async () => {
    const user = await openRole("Area manager");
    const state = async () => ((await (await fetch("/api/v1/health")).json()) as { kill_switch: boolean }).kill_switch;
    await user.click(await screen.findByRole("button", { name: /Stop all suggestions/ }));
    expect(await state()).toBe(false);
    await user.click(screen.getByRole("button", { name: "Yes" }));
    expect(await screen.findByRole("button", { name: /Start suggestions again/ })).toBeInTheDocument();
    expect(await state()).toBe(true);
    await user.click(screen.getByRole("button", { name: /Start suggestions again/ }));
    expect(await state()).toBe(true);
    await user.click(screen.getByRole("button", { name: "Yes" }));
    expect(await screen.findByRole("button", { name: /Stop all suggestions/ })).toBeInTheDocument();
    expect(await state()).toBe(false);
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

describe("dc lead purchases", () => {
  it("records what came from farmer groups and from the mandi, as a record only", async () => {
    const user = await openRole("DC buying lead");
    expect(await screen.findByText("What you bought today")).toBeInTheDocument();
    const tile = (await screen.findAllByRole("button", { name: /Tomato/ })).at(-1) as HTMLElement;
    await user.click(tile);
    for (let i = 0; i < 2; i++) await user.click(screen.getByRole("button", { name: "From the mandi: More" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mock.outcomes).toHaveLength(2));
    expect(mock.outcomes.map((o) => [o.source, o.units_bought])).toEqual([
      ["farmer_group", 0],
      ["spot", 10],
    ]);
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
    await openProduct(user, "Tomato");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    const box = screen.getByPlaceholderText("Type your question");
    await user.type(box, "why?{Enter}");
    expect(await screen.findAllByText("Rain is coming tomorrow, so fewer shoppers will visit.")).not.toHaveLength(0);
    await user.type(box, "what is the capital?{Enter}");
    expect(await screen.findByText("I don't have that.")).toBeInTheDocument();
    expect(mock.asked[0].suggestion_id).toBe("s-order-tomato");
  });
});
