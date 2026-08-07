/**
 * validation.ts — zod schemas for key OUTRENA forms (Task 2-b finding 10).
 *
 * Previously, the package.json declared `zod`, `react-hook-form`, and
 * `@hookform/resolvers` but NONE of the 40+ forms used them. This module
 * defines zod schemas for the 4 audit-flagged key forms:
 *
 *   1. CampaignCreateSchema  — CampaignsPage New Campaign dialog
 *   2. ProspectImportSchema  — ProspectsPage CSV import dialog (URL + raw text)
 *   3. LlmConfigCreateSchema — LlmConfigPage New Config dialog
 *   4. DomainCreateSchema    — DomainsPage New Domain dialog
 *
 * The schemas are intended to be called inline (`Schema.safeParse(form)`)
 * inside the existing `handleSave()` / `handleSubmit()` handlers — they do
 * NOT migrate the forms to react-hook-form (too invasive at this stage).
 * On validation failure the handler shows a sonner toast listing the issues
 * and aborts the API call.
 */
import { z } from "zod";

/** Helper: format a zod error for sonner toast. */
export function formatZodError(err: z.ZodError): string {
  return err.issues
    .map((i) => {
      const path = i.path.length > 0 ? i.path.join(".") + ": " : "";
      return `${path}${i.message}`;
    })
    .join(" · ");
}

/* ── 1. Campaign create ────────────────────────────────────────────────── */

export const CAMPAIGN_FRAMEWORKS = [
  "trigger",
  "challenger",
  "value",
  "meddpicc",
  "spiced",
  "story",
] as const;

export const CampaignCreateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Name must be at least 2 characters")
    .max(120, "Name must be 120 characters or fewer"),
  framework: z.enum(CAMPAIGN_FRAMEWORKS, {
    errorMap: () => ({ message: "Pick a framework" }),
  }),
  gtmThesis: z
    .string()
    .trim()
    .max(800, "GTM thesis must be 800 characters or fewer")
    .optional()
    .or(z.literal("")),
  ownerUserId: z
    .string()
    .min(1, "Pick an owner")
    .optional()
    .or(z.literal("")),
  collateralIds: z.array(z.string()).optional(),
});
export type CampaignCreateInput = z.infer<typeof CampaignCreateSchema>;

/* ── 2. Prospect CSV import ────────────────────────────────────────────── */

export const ProspectImportSchema = z
  .object({
    source: z.enum(["csv", "paste", "url"], {
      errorMap: () => ({ message: "Pick an import source" }),
    }),
    /** Raw CSV/paste text — required when source is `paste` or `csv` (file body). */
    text: z.string().optional(),
    /** URL — required when source is `url`. */
    url: z
      .string()
      .url("Enter a valid URL")
      .optional()
      .or(z.literal("")),
    campaignId: z.string().optional().or(z.literal("")),
  })
  .superRefine((val, ctx) => {
    if (val.source === "url") {
      if (!val.url) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["url"],
          message: "URL is required when source is URL",
        });
      }
    } else {
      if (!val.text || val.text.trim().length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["text"],
          message: "CSV text is required for paste/file import",
        });
      }
      // crude CSV header check: must contain a comma or tab newline.
      if (val.text && !/[,\t]/.test(val.text) && !/\n/.test(val.text)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["text"],
          message: "Doesn't look like CSV — expected commas or tabs",
        });
      }
    }
  });
export type ProspectImportInput = z.infer<typeof ProspectImportSchema>;

/* ── 3. LlmConfig create ───────────────────────────────────────────────── */

export const LLM_PROVIDERS = [
  "zai",
  "openai",
  "anthropic",
  "google",
  "deepseek",
  "groq",
  "mistral",
  "together",
  "fireworks",
  "perplexity",
  "openrouter",
  "ollama",
  "azure",
] as const;

export const LlmConfigCreateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Name must be at least 2 characters")
    .max(120, "Name must be 120 characters or fewer"),
  provider: z.enum(LLM_PROVIDERS, {
    errorMap: () => ({ message: "Pick a provider" }),
  }),
  model: z
    .string()
    .trim()
    .min(1, "Model is required (e.g. gpt-4o)"),
  apiKey: z
    .string()
    .min(8, "API key looks too short (min 8 chars)")
    .optional()
    .or(z.literal("")),
  baseUrl: z
    .string()
    .url("Base URL must be a valid URL")
    .optional()
    .or(z.literal("")),
  temperature: z
    .number()
    .min(0, "Temperature ≥ 0")
    .max(2, "Temperature ≤ 2")
    .optional(),
  maxTokens: z
    .number()
    .int("Max tokens must be an integer")
    .min(1, "Max tokens ≥ 1")
    .max(1_000_000, "Max tokens ≤ 1,000,000")
    .optional(),
  isActive: z.boolean().optional(),
  isDefault: z.boolean().optional(),
});
export type LlmConfigCreateInput = z.infer<typeof LlmConfigCreateSchema>;

/* ── 4. Domain create ──────────────────────────────────────────────────── */

export const DomainCreateSchema = z.object({
  domain: z
    .string()
    .trim()
    .min(3, "Domain is required")
    .regex(
      /^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$/,
      "Enter a valid domain (e.g. acme.com — no scheme, no path)",
    ),
  displayName: z
    .string()
    .max(120, "Display name must be 120 characters or fewer")
    .optional()
    .or(z.literal("")),
  isActive: z.boolean().optional(),
  /** Daily send cap — 0 means uncapped (server enforces). */
  dailySendCap: z
    .number()
    .int("Must be an integer")
    .min(0, "Must be ≥ 0")
    .max(100_000, "Must be ≤ 100,000")
    .optional(),
});
export type DomainCreateInput = z.infer<typeof DomainCreateSchema>;
