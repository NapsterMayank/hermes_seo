# Hermes runbook: process an approved browser batch

Only process rows whose `approval_status` is `approved`. Default batch size is 10.

For each approved prospect:

1. Re-open the exact opportunity page and confirm it still exists, fits the business,
   and permits the intended contribution.
2. If an account is needed and none exists, set the task checkpoint to
   `account-approval` and pause. Continue only after the owner approves that exact
   domain. Never reuse passwords or store passwords, cookies, recovery codes, or OTPs
   in repository files.
3. Fill ordinary fields only after approval. Pause visibly for CAPTCHA, OTP, phone or
   identity verification, terms acceptance, recovery setup, payment, or consent. The
   owner completes or explicitly approves those steps.
4. Draft from `seo/templates/story-submission.md`. Tell a truthful, useful story and
   disclose affiliation. Do not disguise an advertisement as an independent personal
   recommendation.
5. Save the exact draft under `seo/outreach/<domain>.md`, set
   `submission_status=drafted`, and pause for payload approval.
6. Submit only the exact approved payload. Record the result, timestamp, page URL,
   link URL/rel when visible, and evidence path. Never bypass moderation or retry a
   rejected submission through another identity.
7. Save after every site, including failures, so the next session can resume safely.

Finish a batch cleanly so the launcher runs `./seo-campaign sync`, then ask the owner
to review the Excel workbook before approving another batch.
