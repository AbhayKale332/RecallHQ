# Day 1 corpus reconciliation

The approved corpus (`086bc5508ce39553caa680aa775fae194729abee7f025c1d86a8c466fde47c55`)
and the later corpus (`0ad384c45ee886801bd98081097bf1f699ef05abd6643119f936d2e6ad7555a9`)
both had 2,233 rows and identical message IDs, authors, timestamps, parents, and text.
Exactly six rows changed, all in `plants` or `refs`:

| Message ID | Approved tags | Later tags | Reason |
| --- | --- | --- | --- |
| `synthetic:product:20260828-03` | plants `F06` | no plants | Sketch post does not state Leo's review deadline. |
| `synthetic:product:20260828-07` | refs `F06` | plants `F06` | Reply states Leo owns review by 2026-09-03. |
| `synthetic:random:20260924-03` | plants `F34` | no plants | Cafeteria post does not mention Mongo. |
| `synthetic:random:20260924-12` | refs `F34` | plants `F34` | Post contains the Mongo migration joke. |
| `synthetic:eng:20260925-01` | plants `F26` | no plants | Status request does not confirm export completion. |
| `synthetic:eng:20260925-02` | refs `F22, F26` | plants `F26`; refs `F22` | Reply confirms the export is out. |

The approved hash was reproduced from the raw caches and the repairs present at approval.
Applying only the six tag changes reproduced `0ad384c4…`. They are now recorded in
`repairs.yaml`, so a rebuild retains them.

At the time of the `0ad384c4…` rewrite, `queries.yaml` was written after the corpus
(19:14:58 versus 19:14:54 local time), while the append-only verification audit's
last write was earlier (19:13:50). The six tag moves changed no message text, so
existing claim/text verdicts remained applicable, but Q07 and Q11 labels still
needed correction. The current query labels have been updated and validated against
the final corpus. The audit includes historical records; all currently labeled
evidence has a positive verification keyed by its current claim and message text.

The final corpus also repairs the F14 and F21 plant texts. Its SHA-256 is
`d9c6b02135744c0e13bd00333877676c6b388f99952c4ccb37046dc6794fc4e8`.
