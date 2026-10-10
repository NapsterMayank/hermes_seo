# Campaign automation

The CSV files in `seo/data/` are the source of truth. Hermes updates them as it
researches or processes a site. The campaign command normalizes domains, assigns stable
IDs, merges duplicates, rebuilds the next-task queue, and creates an Excel workbook.

```bash
./seo-campaign sync
./seo-campaign summary
./seo-campaign approve P-0001 P-0002 --note "Reviewed in workbook"
./seo-campaign reject P-0003 --note "Not relevant to our audience"
./seo-campaign approve-task T-0042 --note "Account creation approved for this domain"
```

Review `seo/reports/backlink-review.xlsx`. Approval changes should be made with the
command above or in the source CSV, followed by `./seo-campaign sync`; editing the XLSX
does not flow changes back into the campaign.

## Resumable state model

`sync` derives one next browser task per prospect:

1. `qualification` — evidence or scoring is incomplete.
2. `owner-review` — a qualified prospect awaits approval.
3. `account` — the approved site needs an account and exact-domain approval.
4. `draft` — Hermes may prepare the local story draft.
5. `submission` — the exact payload awaits approval.
6. `verification` — capture the published URL and link attributes.

Prospect approval permits preparation for that opportunity. It does not approve an
account or submission. Approve the exact `account-approval` or `payload-approval` task
ID separately with `approve-task`.

Passwords, browser cookies, OTPs, recovery codes, and CAPTCHA data must never be stored
in these files. `account-register.csv` records status only.
