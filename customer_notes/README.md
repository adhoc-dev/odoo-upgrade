# customer_notes — the note as files (alternative 2)

The second of the two alternatives on the table for task 72028. Same channel underneath:
an upgrade script emits what it found with `add_customer_note` and the provider publishes
the note. What changes is **where the message lives**.

- **Alternative 1** (branch `master-t-72028-cos`): the message stays in the upgrade line,
  edited from Odoo. The values reach it namespaced by the note's slug, because nothing
  declares which row belongs to which note — so the message has to say
  `valoracion_stock_accionables['escenario_b_rows']`.
- **Alternative 2** (this directory): the note *is* the folder and the folder is named
  after the slug, so the loader knows which row is this note's and hands it its own
  values. The message says **`escenario_b_rows`**, with no prefix. That prefix is, exactly,
  the price of alternative 1.

## Layout

```
customer_notes/<version>/<module>/NNN-<slug>/
  note.yml     metadata: what today are fields of the upgrade line
  note.html    the message (QWeb) -- the only file a PO touches
  cases/       input fixtures for the preview and the golden test
```

Top-level on purpose, like `pre_odoo_scripts/`: Odoo's loader only descends into
directories named after a module, so a `customer_notes/` at the root is never visited.
Under it, target version first and module second, so a note sits next to the migration
that motivates it.

The prefix `NNN-` is the execution sequence with padding; the order is applied by sorting,
and the display order in the customer's portal is `customer_note_sequence`, which is
metadata and not path.

A note with `source: finding` carries **no code at all**: the detection is the migration
script, and here there is only metadata and a message. That is the case this directory
shows, and it is the majority case the design is after.

## What is built and what is not

Built: the anatomy, and the pilot note ported from upgrade line 2021.

**Not built, and both are deliberate:**

- **The loader on the provider side.** Reading these files requires the provider to have
  the repo checked out and refreshed, which is the hard dependency the spec flags as
  Clarification 1, owned by DevOps + jjs. Until that is answered there is nothing to
  connect, so the files stop at the seam.
- **The golden `expected.html` of each case.** They must come from the *same* render as
  production -- `helpdesk.ticket.customer_note.render()`, QWeb plus its sanitizers -- or
  "it looks fine in the preview" means nothing. That render lives in the provider, so the
  expected files get generated when the renderer lands, not written by hand here.

## The message ported without a single edit

`note.html` is upgrade line 2021's message, byte for byte. Nothing was rewritten, and that
is the point: the message already says `escenario_b_rows`, unprefixed, which is exactly
what the loader hands it.

It is worth putting next to the other alternative. There, the same message had to be
edited -- four replacements -- so it would say
`valoracion_stock_accionables['escenario_b_rows']`. The prefix is what a note pays for
having nothing that declares which row is its own, and it lands on the one file a PO
touches.
