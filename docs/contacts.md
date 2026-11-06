# Store contacts

The area manager can call a store's manager from the Area screen: pick a store, tap the green call button.

- Numbers live in `config/contacts.yaml` (store id, optional name, optional phone). The file ships **empty**: this is a synthetic project and no real people or numbers are stored. Fill it in per store; a store without a number shows a short note instead of a button.
- A phone is digits, spaces and an optional leading `+` only. Anything else is refused when the app starts.
- Only the area manager can read `GET /api/v1/contacts`. Other roles get 403.
- The button is a plain `tel:` link: the phone dials, the app records nothing.

# Why a product used to appear twice

Each daily run added a new set of suggestions with its own ids, and the older ones stayed open until their deadline, so one product could show with two amounts (for example 149 and 132). A newer run now closes older, undecided proposals for the same store, product and kind: they expire with an audit event "superseded by a newer run". Decided suggestions are never touched.
