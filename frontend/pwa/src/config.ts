// Interface settings only. Business limits (discount steps, deadlines, floors) live in the
// server's config/ and are never repeated here.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api/v1";

/** One tap on plus or minus changes the order by this many units. */
export const EDIT_STEP_UNITS = 1;

/** An edit larger than this share of the suggestion asks "are you sure". */
export const LARGE_EDIT_FRACTION = 0.25;

/** Most crate icons drawn in one row; bigger quantities use one icon for several units. */
export const MAX_ICONS = 12;

/** Longest PIN the number pad accepts. */
export const MAX_PIN_LENGTH = 8;
