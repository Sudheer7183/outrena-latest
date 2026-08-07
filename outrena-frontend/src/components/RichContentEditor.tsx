/**
 * RichContentEditor.tsx — Markdown editor with live preview.
 *
 * A reusable rich editor component that provides a split-pane markdown
 * editing experience: a textarea on the left for raw markdown input and
 * a live-rendered preview on the right using react-markdown + remark-gfm.
 *
 * Used by Templates, Collaterals, and other content-editing pages.
 *
 * Props:
 *   value        — controlled markdown source string
 *   onChange     — callback when the source changes
 *   placeholder  — optional placeholder for the textarea
 *   minHeight    — minimum height of the editor (default 300px)
 *   readOnly     — if true, only the preview is shown (no textarea)
 *   className    — additional CSS class for the outer wrapper
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Eye, Edit3, SplitSquareHorizontal } from "lucide-react";

import { cn } from "@/lib/utils";
// import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";

type ViewMode = "edit" | "preview" | "split";

export interface RichContentEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: number;
  readOnly?: boolean;
  className?: string;
}

export function RichContentEditor({
  value,
  onChange,
  placeholder = "Write your content in Markdown…",
  minHeight = 300,
  readOnly = false,
  className,
}: RichContentEditorProps) {
  const [viewMode, setViewMode] = useState<ViewMode>(readOnly ? "preview" : "split");

  return (
    <div className={cn("space-y-2", className)}>
      {/* View mode toggle */}
      {!readOnly && (
        <div className="flex items-center justify-between">
          <Tabs
            value={viewMode}
            onValueChange={(v) => setViewMode(v as ViewMode)}
          >
            <TabsList className="h-8">
              <TabsTrigger value="edit" className="text-xs gap-1">
                <Edit3 className="h-3 w-3" />
                Edit
              </TabsTrigger>
              <TabsTrigger value="split" className="text-xs gap-1">
                <SplitSquareHorizontal className="h-3 w-3" />
                Split
              </TabsTrigger>
              <TabsTrigger value="preview" className="text-xs gap-1">
                <Eye className="h-3 w-3" />
                Preview
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <span className="text-xs text-muted-foreground">
            {value.length} chars
          </span>
        </div>
      )}

      {/* Editor + Preview panes */}
      <div
        className="grid gap-2 rounded-md border"
        style={{
          gridTemplateColumns:
            viewMode === "split"
              ? "1fr 1fr"
              : "1fr",
          minHeight,
        }}
      >
        {/* Edit pane */}
        {(viewMode === "edit" || viewMode === "split") && !readOnly && (
          <div className="relative">
            <Textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={placeholder}
              className="h-full min-h-[inherit] resize-none rounded-none border-0 font-mono text-sm focus-visible:ring-0"
              style={{ minHeight }}
            />
          </div>
        )}

        {/* Preview pane */}
        {(viewMode === "preview" || viewMode === "split") && (
          <ScrollArea className="p-4" style={{ minHeight }}>
            {value.trim() ? (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {value}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {readOnly ? "No content." : "Start typing to see a preview…"}
              </p>
            )}
          </ScrollArea>
        )}
      </div>
    </div>
  );
}
