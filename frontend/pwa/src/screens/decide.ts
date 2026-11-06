import { ApiError, api } from "../api/client";
import type { Approval, Role } from "../api/types";

/**
 * Send one decision for every step on a card. A step already decided (409) counts as done, so a
 * second tap or a slow connection never shows an error for work that went through.
 * "done" means at least one step was recorded and the list should reload.
 */
export async function decideAll(
  role: Role,
  ids: string[],
  body: { action: Approval["action"]; edited_units?: number; reason?: string },
): Promise<"done" | "failed"> {
  let recorded = 0;
  for (const id of ids) {
    try {
      await api.decide(role, id, body);
      recorded += 1;
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        recorded += 1;
        continue;
      }
      return recorded > 0 ? "done" : "failed";
    }
  }
  return "done";
}
