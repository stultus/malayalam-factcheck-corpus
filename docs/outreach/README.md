# Permission outreach

Templates and per-source contact log for asking IFCN signatories
for written permission to redistribute their fact-check articles
(specifically `evidence_text`) as part of the corpus.

## Why this exists

Fact-check article bodies are editorial work product. Local research use
sits inside Indian fair dealing; *redistributing* the prose to third
parties does not. The default release form for the corpus is therefore
URLs + structured fields + canonical labels + a re-fetch script (see the
"publishable subset" tier in `LEGAL.md` and the `mfc rehydrate` script).

For sources whose publishers grant explicit permission, we can move from
the labels-overlay tier to a richer tier that ships the full
`evidence_text`. That permission is recorded in
`configs/malayalam_factcheck_sources.json` as `permission_status`
∈ {`unasked`, `requested`, `granted`, `denied`}, and the publishable
writer reads from there.

## Files (TBD)

- `email_template.md` — short request email; one template, lightly
  customised per outlet.
- `log.csv` — append-only contact log: `source_id`, `contacted_at`,
  `recipient`, `subject`, `outcome`, `notes`. Updates here drive
  `permission_status` updates in the sources JSON.

Both deferred per task #33 — the user will draft the template when
ready to start outreach.
