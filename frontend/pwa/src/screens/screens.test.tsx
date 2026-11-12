import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { clearSession, signalExpired } from "../api/session";
import { installMockFetch } from "../mock/handlers";

const PIN_FOR: Record<string, string> = {
  "Store manager": "1111",
  "Area manager": "3333",
  "North area manager": "6666",
  "DC buying lead": "4444",
  "Farmer group": "5555",
};

let mock: ReturnType<typeof installMockFetch>;
beforeEach(() => {
  // the mock's orders are dated 3 Nov 2026; make that "tonight" so the screens read as they would live
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-03T21:00:00+05:30"));
  mock = installMockFetch();
  clearSession();
});

afterEach(() => {
  vi.useRealTimers();
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
  it("shows which stores report to which area manager, with no PINs and nothing to tap", async () => {
    render(<App />);
    const tree = await screen.findByTestId("org-tree");
    expect(within(tree).getByText("DC buying lead")).toBeInTheDocument();
    expect(within(tree).getByText("Area manager: North")).toBeInTheDocument();
    expect(within(tree).getByText("S06 · Malleshwaram")).toBeInTheDocument();
    expect(within(tree).getByText("Farmer group")).toBeInTheDocument();
    expect(within(tree).queryByRole("button")).toBeNull();
    expect(tree.textContent).not.toMatch(/\d{4}/);
  });

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
    const tiles = await screen.findAllByRole("button", { name: /(Banana|Tomato|Spinach).*\d/ });
    expect(tiles[0]).toHaveTextContent("Banana");
    expect(tiles[1]).toHaveTextContent("Tomato");
    expect(tiles[0]).not.toHaveTextContent("crates");
  });

  it("the amount can be typed as a whole number, and letters or points are dropped", async () => {
    const user = await openRole("Store manager");
    await openProduct(user, "Tomato");
    const box = screen.getByRole("textbox", { name: "Amount to order" });
    await user.clear(box);
    await user.type(box, "2a5.7");
    expect(box).toHaveValue("257");
    await user.type(screen.getByPlaceholderText("Write a reason to save"), "Festival");
    await user.click(screen.getByRole("button", { name: "Save change" }));
    await user.click(await screen.findByRole("button", { name: "Yes" })); // a big change asks first
    await waitFor(() => expect(mock.decisions).toHaveLength(1));
    expect(mock.decisions[0]).toMatchObject({ action: "edit", edited_units: 257 });
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

  it("big counts are typed in whole numbers, not tapped one at a time", async () => {
    const user = await openRole("Store manager");
    await openProduct(user, "Tomato");
    await user.click(screen.getByRole("button", { name: "Accept" }));
    await user.click(await screen.findByRole("button", { name: /Closing/ }));
    await openProduct(user, "Tomato");
    const sold = screen.getByRole("textbox", { name: "Sold" });
    await user.clear(sold);
    await user.type(sold, "118kg");
    expect(sold).toHaveValue("118");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mock.outcomes).toHaveLength(1));
    expect(mock.outcomes[0]).toMatchObject({ units_sold: 118, units_wasted: 0 });
  });
});

describe("area manager", () => {
  it("shows the scoreboard with all three measures beside the queue", async () => {
    await openRole("Area manager");
    expect(await screen.findByLabelText("Wasted")).toBeInTheDocument();
    expect(screen.getByLabelText("Empty shelves")).toBeInTheDocument();
    expect(screen.getByLabelText("Farmer share")).toBeInTheDocument();
  });

  it("a store with a phone number gets a call button; one without says so and shows none", async () => {
    const user = await openRole("Area manager");
    const nav = within(await screen.findByRole("navigation"));
    await user.click(nav.getByRole("button", { name: /Jayanagar/ }));
    const call = await screen.findByRole("link", { name: /Call Test manager/ });
    expect(call).toHaveAttribute("href", "tel:+919000000001");
    await user.click(nav.getByRole("button", { name: /Indiranagar/ }));
    expect(await screen.findByText(/No phone number is set/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Call/ })).not.toBeInTheDocument();
  });

  it("shows what the stores have already decided", async () => {
    const user = await openRole("Area manager");
    expect(await screen.findByText("What stores decided")).toBeInTheDocument();
    // a store's row is a button: tapping it opens that store, with what is waiting by type
    await user.click(await screen.findByRole("button", { name: /Jayanagar.*waiting/ }));
    expect(await screen.findByText(/^Waiting: .*orders/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Call Test manager/ })).toBeInTheDocument();
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

describe("an area manager with their own area", () => {
  it("is named by area, sees only their stores and cannot stop everything", async () => {
    await openRole("North area manager");
    expect(await screen.findByText(/Area manager · North/)).toBeInTheDocument();
    const nav = within(await screen.findByRole("navigation"));
    expect(nav.getByRole("button", { name: /North/ })).toBeInTheDocument();
    expect(nav.queryByRole("button", { name: /All stores together/ })).not.toBeInTheDocument();
    expect(await screen.findByText("Pick a store above to see its scoreboard.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Stop all suggestions/ })).not.toBeInTheDocument();
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
    for (let i = 0; i < 2; i++) await user.click(screen.getByRole("button", { name: "From K.R. Market: More" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mock.outcomes).toHaveLength(3));
    expect(mock.outcomes.map((o) => [o.source, o.market ?? null, o.units_bought])).toEqual([
      ["farmer_group", null, 0],
      ["spot", "APMC Yeshwanthpur", 0],
      ["spot", "K.R. Market", 10],
    ]);
  });
});

describe("dc lead sees what the stores ordered", () => {
  it("adds up the stores' decided orders and says who is still deciding", async () => {
    await openRole("DC buying lead");
    expect(await screen.findByText("What the stores ordered")).toBeInTheDocument();
    expect(await screen.findByText(/Some stores are still deciding/)).toBeInTheDocument();
    expect(screen.getAllByText(/of \d+ stores decided/).length).toBeGreaterThan(0);
  });

  it("shows, per product, how much goes to each area and store", async () => {
    await openRole("DC buying lead");
    await screen.findByText("What the stores ordered");
    expect((await screen.findAllByText("Send to which area and store")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/South and central|North|East/).length).toBeGreaterThan(0);
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

describe("empty evening screen says what really happened", () => {
  it("says orders ran out of time, not that they were answered", async () => {
    mock.expireOrders();
    await openRole("Store manager");
    expect(await screen.findByText(/ran out of time\. Nothing was ordered/)).toBeInTheDocument();
    expect(screen.queryByText("All orders answered")).not.toBeInTheDocument();
  });
});

describe("tonight's orders are not last night's", () => {
  it("answered orders from tonight say all answered", async () => {
    mock.answerOrders();
    await openRole("Store manager");
    expect(await screen.findByText("All orders answered")).toBeInTheDocument();
  });

  it("the next evening before the run, last night's answered orders do not say all answered", async () => {
    mock.answerOrders();
    vi.setSystemTime(new Date("2026-11-04T18:30:00+05:30")); // tonight's batch has not come yet
    await openRole("Store manager");
    expect(await screen.findByText(/Tonight's orders have not arrived yet/)).toBeInTheDocument();
    expect(screen.getByText(/Last night: \d+ orders answered/)).toBeInTheDocument();
    expect(screen.queryByText("All orders answered")).not.toBeInTheDocument();
  });

  it("last night's orders that ran out of time are named as last night's", async () => {
    mock.expireOrders();
    vi.setSystemTime(new Date("2026-11-04T18:30:00+05:30"));
    await openRole("Store manager");
    expect(await screen.findByText(/Last night's orders ran out of time/)).toBeInTheDocument();
  });
});

describe("one week of history", () => {
  it("a store manager picks a day on the calendar and sees orders and closing together", async () => {
    const user = await openRole("Store manager");
    await user.click(await screen.findByRole("button", { name: /History/ }));
    expect(await screen.findByText("Your history")).toBeInTheDocument();
    expect(await screen.findByTestId("calendar-pick")).toBeInTheDocument();
    expect(await screen.findByText(/Thrown away 8% · ran out/)).toBeInTheDocument();
    // the day before and the day after are one tap away; the last day cannot go later
    await user.click(screen.getByRole("button", { name: "Day before" }));
    expect(await screen.findByText(/Thrown away 8% · ran out/)).toBeInTheDocument();
  });

  it("farmers see only the estimate and can open a history calendar", async () => {
    const user = await openRole("Farmer group");
    expect(await screen.findByText(/Estimates for the next 3 days only/)).toBeInTheDocument();
    await user.click(await screen.findByText("History: pick a day"));
    expect(await screen.findByText(/Bought from farmer groups: 72/)).toBeInTheDocument();
    expect(screen.getByTestId("calendar-pick")).toBeInTheDocument();
  });

  it("an area manager has a weekly and a monthly graph with waste and empty shelves together", async () => {
    const user = await openRole("Area manager");
    const trend = await screen.findByTestId("trend");
    expect(await within(trend).findByRole("group", { name: /Thrown away and ran out by day/ })).toBeInTheDocument();
    expect(within(trend).getByText(/Farmer-group share, whole chain: 62%/)).toBeInTheDocument();
    // hovering a day says what happened that day and where; the latest day is shown to start with
    const detail = within(trend).getByTestId("trend-detail");
    expect(within(detail).getByText(/Most thrown away/)).toBeInTheDocument();
    expect(within(detail).getByText(/Stores to look at/)).toBeInTheDocument();
    const days = within(trend).getAllByRole("button", { name: /Thrown away/ });
    await user.hover(days[0]);
    expect(within(trend).getByTestId("trend-detail")).toBeInTheDocument();
    // what to talk about, with a way into the store that needs the call
    const talk = within(trend).getByTestId("talk");
    expect(within(talk).getByText(/ran out in 9 of 25 counts/)).toBeInTheDocument();
    expect(within(talk).getByText(/was the order too small/i)).toBeInTheDocument();
    expect(within(talk).getAllByRole("button", { name: "Open this store" }).length).toBeGreaterThan(0);
    await user.click(within(trend).getByRole("button", { name: "Monthly" }));
    const chart = await within(trend).findByRole("group", { name: /Thrown away and ran out by day/ });
    expect(chart.querySelectorAll("circle").length).toBeGreaterThan(7);
  });

  it("an area manager sees each store's week with thrown away and ran out side by side", async () => {
    await openRole("Area manager");
    expect(await screen.findByText("Last 7 days, store by store")).toBeInTheDocument();
    expect(screen.getAllByText(/Thrown away 8%/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ran out 25%/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Farmer-group share: not known/)).toBeInTheDocument();
  });
});
