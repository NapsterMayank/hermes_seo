# Connection checklist

Never paste secrets into this repository. Store credentials through `hermes tools`, the provider's OAuth flow, or `~/.hermes/.env` when the Hermes documentation explicitly calls for an environment variable.

## Ready now

- [x] Local Ollama model with tool calling
- [x] 65,536-token agent context
- [x] Playwright Chromium and headless shell
- [x] Hermes built-in browser tools
- [x] Browser Use CLI installed for future use with a stronger model or cloud browser
- [x] Tavily keyless web search and extraction
- [x] Project-local `seo-geo-operator` skill
- [x] Content, backlink-prospect, and outreach tracking templates

## Requires owner authentication

### Website identity

- [ ] Complete `seo/project.yaml`
- [ ] Confirm the canonical website URL and target markets
- [ ] Confirm approved business claims and named authors/reviewers

### Google Search Console and GA4

- [ ] Sign in with an account that can access the correct Search Console property
- [ ] Record the property URL or `sc-domain:` identifier (not a credential)
- [ ] Confirm the GA4 property ID
- [ ] Grant read-only access first
- [ ] Verify one Search Console query report and one GA4 landing-page report

### Bing Webmaster Tools

- [ ] Verify/import the site
- [ ] Confirm sitemap status
- [ ] Use read-only reporting until the indexing workflow is reviewed

### CMS

- [ ] Identify WordPress, Webflow, Git, or another CMS
- [ ] Create a least-privileged integration identity
- [ ] Limit initial access to reading and creating drafts
- [ ] Create and review one test draft
- [ ] Keep automatic publication disabled

For WordPress, prefer an application password belonging to a dedicated Editor account rather than the owner's primary administrator password.

### Outreach mailbox

- [ ] Confirm the sending domain and mailbox
- [ ] Verify SPF, DKIM, and DMARC
- [ ] Connect Gmail/Outlook through OAuth or configure the approved Hermes email integration
- [ ] Keep sending review-gated
- [ ] Send a test message to an address owned by the user
- [ ] Define the daily cap, follow-up limit, and opt-out process

### Backlink and competitor data

- [ ] Select SE Ranking, Ahrefs, Semrush, Majestic, or another provider
- [ ] Connect read-only API access where available
- [ ] Verify referring-domain and competitor-gap reports for the correct domain

### Vision and fallback model

- [ ] Select a vision-capable provider for screenshots and visual audits
- [ ] Select a stronger fallback model for difficult multi-step browser work
- [ ] Test fallback without changing the local Ollama model as the default

## Approval boundary

The owner must approve the exact target and payload before account creation, terms acceptance, CMS publication, outreach sending, purchases, credential changes, or destructive changes. CAPTCHA, OTP, phone verification, identity verification, payment, and account recovery remain human-only.

