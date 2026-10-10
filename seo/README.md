# SEO/GEO Operations

This directory is the working record for research, content production, backlink outreach, and measurement. It intentionally contains no credentials.

Start by completing `project.yaml`. Then copy the templates into the appropriate working directories:

- `templates/content-brief.md` → `briefs/<slug>.md`
- completed content → `drafts/<slug>.md`
- approved outreach drafts → `outreach/<domain>.md`
- prospect and outreach status → `data/*.csv`

Start the focused local agent from the repository root:

```bash
./seo-agent
```

The launcher first opens a visible Brave window using the dedicated persistent
profile in `browser-profile/`, then exposes only browser, web, and file tools.
Log in to the campaign email and complete human verification in that window; do
not use your personal Brave profile. The dedicated profile is ignored by Git.

This smaller tool schema is
intentional: it makes tool calls substantially more reliable on the local 8B
model. When Hermes exits, the launcher automatically runs the campaign synchronizer
and refreshes the Excel workbook. Use the project skill directly from another Hermes session when a wider
toolset is required:

```text
/seo-geo-operator audit the website and produce a prioritized plan
```

External actions are review-gated. Research and local drafts may proceed without approval; account creation, CMS writes, publishing, email sending, purchases, CAPTCHA, OTP, identity verification, and terms acceptance require human review.

## Repeated backlink campaign

Use the two runbooks as Hermes prompts:

- `prompts/discover-500.md` discovers, verifies, scores, and deduplicates the first
  500 unique domains without creating accounts or posting.
- `prompts/process-approved-batch.md` resumes only owner-approved rows and prepares
  truthful story-based contributions in batches of 10.

After any batch, normalize the queues and regenerate the review workbook:

```bash
./seo-campaign sync
```

The Excel output is `reports/backlink-review.xlsx`. CSV remains the source of truth.
Approve exact prospect IDs with `./seo-campaign approve P-0001 P-0002`; rejection uses
the matching `reject` command. See `automation/README.md` for the state model.

Once the business fields in `project.yaml` are complete, the repeated commands are:

```bash
./seo-discover
./seo-approved-batch
```

Each command processes a bounded batch, saves state, exits, and regenerates the
workbook. Account or payload checkpoints use an exact task approval such as
`./seo-campaign approve-task T-0042`.

If a site displays a robot check, CAPTCHA, OTP, consent screen, or identity check,
Hermes must pause. Complete it manually in the visible Brave window and tell Hermes
to continue. Changing to DuckDuckGo or another headless browser does not remove those
checks; DuckDuckGo Browser also does not expose the Chromium debugging interface used
by Hermes. Run `./seo-browser` whenever you only want to open the campaign browser.
