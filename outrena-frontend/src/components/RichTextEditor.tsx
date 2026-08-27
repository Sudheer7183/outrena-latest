/**
 * RichTextEditor.tsx — Tiptap-based WYSIWYG email editor.
 *
 * Replaces the previous Markdown split-pane RichContentEditor on all email
 * template and sequence editing surfaces. Outputs clean HTML directly, which
 * MailBridge sends with Content-Type: text/html.
 *
 * Props:
 *   value        — controlled HTML string (empty string = blank editor)
 *   onChange     — called with the new HTML string on every edit
 *   placeholder  — editor placeholder text
 *   minHeight    — minimum content area height in px (default 280)
 *   readOnly     — if true, renders as a styled HTML preview (no toolbar)
 *   className    — additional class for the outer wrapper
 *   variables    — merge-tag tokens shown as clickable insertion chips
 *
 * Dependencies (add to package.json then run npm install locally first):
 *   @tiptap/react, @tiptap/pm, @tiptap/starter-kit,
 *   @tiptap/extension-underline, @tiptap/extension-link,
 *   @tiptap/extension-placeholder
 */
import "./RichTextEditor.css";

import { useCallback, useEffect } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Bold,
  Heading2,
  Italic,
  Link2,
  Link2Off,       // ← was LinkOff — renamed in lucide-react v0.383+
  List,
  ListOrdered,
  Pilcrow,
  Redo2,
  UnderlineIcon,
  Undo2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  minHeight?: number;
  readOnly?: boolean;
  className?: string;
  /** Merge-tag tokens shown as clickable insertion chips. */
  variables?: string[];
}

/* ── Toolbar button ──────────────────────────────────────────────────────── */

interface ToolbarButtonProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}

function ToolbarButton({ onClick, active, disabled, title, children }: ToolbarButtonProps) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "ghost"}
      size="icon"
      className="h-7 w-7 shrink-0"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
    >
      {children}
    </Button>
  );
}

/** Thin vertical divider for the toolbar. */
function ToolbarDivider() {
  return <div className="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden />;
}

/* ── Component ───────────────────────────────────────────────────────────── */

export function RichTextEditor({
  value,
  onChange,
  placeholder = "Write your email body…",
  minHeight = 280,
  readOnly = false,
  className,
  variables = [],
}: RichTextEditorProps) {
  /* ── Editor init ── */
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Disable block-level code — not appropriate for email templates.
        codeBlock: false,
        // Disable inline code — not needed for cold email copy.
        code: false,
        // Only expose heading level 2 (enough for email section headers).
        heading: { levels: [2] },
      }),
      Underline,
      Link.configure({
        // Don't navigate away when clicking links inside the editor.
        openOnClick: false,
        HTMLAttributes: {
          // Inline style ensures links render in most email clients.
          style: "color: inherit; text-decoration: underline;",
        },
      }),
      Placeholder.configure({ placeholder }),
    ],
    content: value,
    editable: !readOnly,
    // Explicitly type the callback parameter so TS doesn't infer `any`
    // when Tiptap types are being resolved for the first time.
    onUpdate: ({ editor: e }: { editor: Editor }) => {
      const html = e.getHTML();
      // Treat a single empty paragraph as empty string so callers
      // can easily check for "no content".
      onChange(html === "<p></p>" ? "" : html);
    },
  });

  /* ── Sync external value → editor ── */
  // This fires when the AI or parent programmatically replaces the content
  // (e.g., loading a saved template). Safe against infinite loops because
  // onUpdate above sets parent state to editor.getHTML(), so the next
  // render's `value` will equal editorHtml and the condition will be false.
  useEffect(() => {
    if (!editor) return;
    const editorHtml = editor.getHTML();
    const normalised = editorHtml === "<p></p>" ? "" : editorHtml;
    if (value !== normalised) {
      editor.commands.setContent(value || "");
    }
  }, [value, editor]);

  /* ── Link insert/edit ── */
  const handleSetLink = useCallback(() => {
    if (!editor) return;
    const existing = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Enter URL:", existing ?? "https://");
    if (url === null) return; // user cancelled
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }, [editor]);

  /* ── Cleanup ── */
  useEffect(() => {
    return () => {
      editor?.destroy();
    };
  }, [editor]);

  if (!editor) return null;

  /* ── Read-only HTML preview ── */
  if (readOnly) {
    return (
      <div
        className={cn(
          "outrena-rte rounded-md border bg-background",
          className,
        )}
      >
        <div
          className="outrena-rte-content px-4 py-3 text-sm"
          style={{ minHeight }}
          dangerouslySetInnerHTML={{ __html: value }}
        />
      </div>
    );
  }

  /* ── Editable ── */
  return (
    <div
      className={cn(
        "outrena-rte rounded-md border bg-background transition-shadow",
        className,
      )}
    >
      {/* ── Formatting toolbar ── */}
      <div className="flex flex-wrap items-center gap-0.5 border-b bg-muted/40 p-1">
        {/* Text style */}
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive("bold")}
          title="Bold (Ctrl+B)"
        >
          <Bold className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive("italic")}
          title="Italic (Ctrl+I)"
        >
          <Italic className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          active={editor.isActive("underline")}
          title="Underline (Ctrl+U)"
        >
          <UnderlineIcon className="h-3.5 w-3.5" />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Block type */}
        <ToolbarButton
          onClick={() => editor.chain().focus().setParagraph().run()}
          active={editor.isActive("paragraph")}
          title="Paragraph"
        >
          <Pilcrow className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 2 }).run()
          }
          active={editor.isActive("heading", { level: 2 })}
          title="Heading"
        >
          <Heading2 className="h-3.5 w-3.5" />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Lists */}
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive("bulletList")}
          title="Bullet list"
        >
          <List className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive("orderedList")}
          title="Numbered list"
        >
          <ListOrdered className="h-3.5 w-3.5" />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Links */}
        <ToolbarButton
          onClick={handleSetLink}
          active={editor.isActive("link")}
          title="Insert / edit link"
        >
          <Link2 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().unsetLink().run()}
          disabled={!editor.isActive("link")}
          title="Remove link"
        >
          <Link2Off className="h-3.5 w-3.5" />   {/* ← was LinkOff */}
        </ToolbarButton>

        <ToolbarDivider />

        {/* History */}
        <ToolbarButton
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Undo (Ctrl+Z)"
        >
          <Undo2 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Redo (Ctrl+Y)"
        >
          <Redo2 className="h-3.5 w-3.5" />
        </ToolbarButton>
      </div>

      {/* ── Merge-tag variable chips ── */}
      {variables.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 border-b bg-muted/20 px-2 py-1.5">
          <span className="shrink-0 text-xs text-muted-foreground">
            Insert variable:
          </span>
          {variables.map((v) => (
            <Badge
              key={v}
              variant="outline"
              className="cursor-pointer font-mono text-xs transition-colors hover:bg-primary/10"
              onClick={() => {
                editor.chain().focus().insertContent(v).run();
              }}
            >
              {v}
            </Badge>
          ))}
        </div>
      )}

      {/* ── Editor canvas ── */}
      <ScrollArea>
        <EditorContent
          editor={editor}
          className="outrena-rte-content text-sm"
          style={{ minHeight }}
        />
      </ScrollArea>

      {/* ── Character count ── */}
      <div className="border-t px-3 py-1 text-right text-xs text-muted-foreground">
        {editor.getText().length} chars
      </div>
    </div>
  );
}

export default RichTextEditor;
