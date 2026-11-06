# Three areas, three area managers

`config/areas.yaml` groups the 12 stores into three areas by how close they are. **This grouping is assumed:** the data pack has no store addresses or distances, so the stores are grouped by the approximate map position of their locality. Replace it with real addresses and regroup if the owner wants.

| Area | Stores |
|---|---|
| South and central | Jayanagar, Indiranagar, Koramangala, HSR Layout, Banashankari, Electronic City |
| North | Malleshwaram, Yelahanka, Hebbal |
| East | Whitefield, Bellandur, Marathahalli |

An area manager's sign-in carries an `area_id` (in the `pin-directory` secret). That manager:

- sees and decides only suggestions for their stores (another area's suggestion looks like it does not exist),
- sees scoreboards, recorded counts, contacts, outcomes and audit for their stores only, and no chain-wide scoreboard,
- cannot use the kill switch. Only an area manager with no area (all stores) can stop every suggestion.

A sign-in with no `area_id` is unchanged and sees every store. The DC lead and farmer coordinator are not limited by area. Store managers still see only their own store.

An unknown `area_id`, or a store listed in two areas, stops the app from starting rather than quietly showing the wrong stores.
