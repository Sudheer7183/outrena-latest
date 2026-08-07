# Help Guide Screenshots

This folder holds PNG screenshots referenced by Help Guide articles
(`src/features/help_guide/HelpGuidePage.tsx` + the `0008_help_content_expansion`
Alembic seed).

## Why a screenshots folder?

Both the legacy HTML guide (`OUTRENA-Help-Guide-v2.html`) and the prior
React help page shipped **zero** screenshots — the audit
(`docs/AUDIT-HELP-1.md` / H-3) flagged this as a "should fix". This
folder + the `<HelpScreenshot>` component make the help guide
"screenshot-ready": dropping a PNG into this folder auto-renders it
inside the relevant article, with click-to-zoom and a friendly
"Screenshot coming soon" placeholder while the PNG is missing.

## Naming convention

```
{section-slug}-{step-number-or-short-slug}.png
```

Examples:

| File | Article |
|---|---|
| `getting-started-welcome.png` | `getting-started/welcome` |
| `admin-setup-connecting-llm.png` | `admin-setup/connecting-llm` |
| `campaigns-sequences-first-campaign.png` | `campaigns-sequences/first-campaign` |
| `campaigns-sequences-email-studio.png` | `campaigns-sequences/email-studio` |
| `deliverability-managing-domains.png` | `deliverability/managing-domains` |
| `icp-prospects-csv-import.png` | `icp-prospects/csv-import` |

Rules:

- **Lowercase kebab-case**, no spaces.
- Use the **section slug** (matches `help_sections.slug` in the DB)
  as the prefix — this lets a future admin search for all screenshots
  for a section.
- Step numbers are optional — use a short descriptive slug instead when
  the article has many screenshots (`-dns-records`,
  `-spf-dkim-dmarc`).
- Avoid version numbers in the filename — overwrite the file when the
  UI changes. The "Last updated" date is recorded in git.

## Capture guidelines

- **Viewport:** 1440 × 900 px (Chrome DevTools "Responsive" preset).
- **Aspect ratio:** 16:10 landscape (matches a typical user's screen).
- **Format:** PNG (lossless, sharp text). JPEG only for photograph-like
  content (rare in an admin UI).
- **Max file size:** 200 KB per screenshot. Use `pngquant --quality=70-90`
  or `oxipng -o 3` to compress — text stays crisp.
- **Anonymize:** blur or replace real customer names, emails, phone
  numbers, API keys, tenant slugs before committing. The staging
  environment's seed data uses `acme.com` / `example.com` placeholders
  — capture against staging, not production.
- **Highlight:** when the article says "click the **Create Campaign**
  button", draw a 2-px solid `#f59e0b` (amber-500) rectangle around
  the button. Use [ShareX](https://getsharex.com/) or
  [Flameshot](https://flameshot.org/) for annotation.
- **Locale:** capture in `en-US`. If the help guide is later
  internationalized, capture per-locale variants in
  `help-screenshots/{locale}/...`.

## How to add a screenshot

1. Save the PNG into this folder using the naming convention above.
2. Open the article body in the `0008_help_content_expansion`
   migration (or via the future admin UI) and add a markdown image:

   ```markdown
   ![Connecting an LLM model](/help-screenshots/admin-setup-connecting-llm.png)
   ```

3. The `<HelpScreenshot>` component (wired into `ArticleBody`'s
   markdown `img` renderer) will lazy-load the image, show a
   "Screenshot coming soon" placeholder if the file is missing or
   fails to load, and open a click-to-zoom Dialog on click.
4. Commit both the PNG and the migration edit.

## Current screenshots (committed)

Captured at 1440x900 px (Chrome headless, light mode), anonymized to
`acme.com` / `acme.io` sample data, annotated with a red dashed outline +
numbered red circle around the key UI element each article steps through.

| File | Article | What it shows |
|---|---|---|
| `getting-started-welcome.png` | `getting-started/welcome` | User dashboard - 4 KPI tiles (emails/replies/meetings/pipeline), today's quota card with progress bar, 7-day stacked-bar activity chart, My Campaigns table, Sender Identities card. Annotation (1) on the KPI tiles row. |
| `admin-setup-connecting-llm.png` | `admin-setup/connecting-llm` | LLM Models table (3 mock configs: openai/gpt-4o-mini active, anthropic/claude-3-5-sonnet inactive, deepseek/deepseek-chat inactive) with masked API keys + per-row Test/Edit/Delete actions. Annotation (1) on the **Add Model** button (top-right). |
| `campaigns-sequences-first-campaign.png` | `campaigns-sequences/first-campaign` | Campaigns list table (6 mock campaigns) with status badges + the **New Campaign** dialog open as a modal overlay - Name / Framework / GTM Thesis / Owner / Collaterals form. Annotation (1) on the **Create Campaign** button (dialog footer). |
| `campaigns-sequences-email-studio.png` | `campaigns-sequences/email-studio` | Email Studio 3-column layout - Generation form (Prospect/Campaign/Touch/Tone/Angle/Max length), Preview pane (subject + body textarea + QA score / Personalisation / Manual review tiles), Anti-Pattern Scan + Compliance Check cards. Annotation (1) on the **Generate** button. |
| `deliverability-managing-domains.png` | `deliverability/managing-domains` | Sending Domains table (3 mock domains: mail.acme.io all-pass, outreach.acme.io DKIM fail, go.acme.io pending) with SPF/DKIM/DMARC pass/fail/unknown badges. Annotation (1) on the **Check DNS** action for the unverified domain. |
| `icp-prospects-csv-import.png` | `icp-prospects/csv-import` | Prospects list table (6 mock prospects with ICP score bars) + the **Import Prospects (CSV)** dialog open as a modal overlay - file dropzone, ICP profile selector, suppression list selector. Annotation (1) on the file dropzone. |

Each PNG is under 60 KB (well within the 200 KB cap) thanks to 8-bit palette
quantization - text stays crisp at 1x zoom and click-to-zoom.

Pending capture (referenced in `0008_help_content_expansion.py`):

- `admin-setup-connecting-llm.png` — Setup → LLM Models → Add Model dialog.
- `campaigns-sequences-first-campaign.png` — Outreach → Campaigns → Create Campaign.
- `campaigns-sequences-email-studio.png` — Outreach → Email Studio → AI Copy Generation panel.
- `deliverability-managing-domains.png` — Setup → Domains → DNS records table.
- `icp-prospects-csv-import.png` — Prospecting → Prospects → Import CSV modal.
