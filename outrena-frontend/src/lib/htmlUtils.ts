/**
 * htmlUtils.ts — Utility functions for the email body HTML pipeline.
 *
 * Used by TemplatesPage and SequencesPage to bridge between legacy Jinja2
 * plain-text bodies and the new HTML-first storage from RichTextEditor.
 *
 * Jinja2 variables in this project use the `{{ var_name }}` format with
 * spaces. These survive HTML storage fine — Tiptap stores them as text nodes
 * inside <p> elements, and the backend's Jinja2 renderer substitutes them
 * in the HTML string before sending.
 */

/**
 * Ensures a string is valid HTML suitable for loading into the Tiptap editor.
 *
 * - Already HTML (starts with a tag): returned as-is.
 * - Plain text (including Jinja2 template bodies with \n\n paragraphs):
 *   each double-newline block becomes a <p>, single \n becomes <br>.
 * - Empty input: returns empty string (Tiptap shows placeholder).
 */
export function ensureHtml(content: string | null | undefined): string {
  if (!content) return "";
  const trimmed = content.trim();
  if (!trimmed) return "";

  // Already HTML: starts with an opening tag and has at least one closing tag.
  if (/^<[a-zA-Z]/.test(trimmed) && /<\/[a-zA-Z]/.test(trimmed)) {
    return content;
  }

  // Plain text / Jinja2 template → HTML paragraphs.
  return trimmed
    .split(/\n{2,}/)
    .filter(Boolean)
    .map((block) => `<p>${block.trim().replace(/\n/g, "<br>")}</p>`)
    .join("");
}

/**
 * Strips all HTML tags and decodes common entities.
 * Used for card preview text and word-count calculations.
 */
export function stripHtml(html: string | null | undefined): string {
  if (!html) return "";
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<\/p>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/**
 * Returns true when the body string is HTML output from the Tiptap RTE,
 * as opposed to legacy plain text.
 *
 * Used by the backend scheduler patch to route body correctly through
 * body_html vs body_text MailBridge fields.
 */
export function isHtmlBody(body: string | null | undefined): boolean {
  if (!body) return false;
  const s = body.trimStart();
  return (
    s.startsWith("<") &&
    (s.includes("</p>") ||
      s.includes("</h") ||
      s.includes("<br") ||
      s.includes("</ul>") ||
      s.includes("</ol>") ||
      s.includes("</li>") ||
      s.includes("</strong>") ||
      s.includes("</em>"))
  );
}
