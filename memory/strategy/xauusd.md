# XAUUSD Strategy Notes

- Symbol: XAUUSD (Gold)
- Preset config: **D40/D20**, TP **2R**, risk **1%** (editable in the Strategy page)
- News filter required; avoid trading during high-impact USD news.
- Real account requires manual confirmation in early phase.
- Manual trade proposals persist risk snapshots and submit only through
  `OrderService`.
- Exact D40/D20 signal semantics are still undefined. Do not infer or enable
  automatic signals until the user confirms the rules.

_Proposal foundation implemented; automatic signal evaluation remains pending._
