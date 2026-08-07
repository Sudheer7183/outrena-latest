/**
 * SupportPage.tsx — in-app support ticket UI.
 *
 * Two-pane layout:
 *   - Left: ticket list with status filter
 *   - Right: selected ticket detail (messages thread + reply + close button)
 *
 * APIs:
 *   - GET /support/tickets → list
 *   - POST /support/tickets → create
 *   - GET /support/tickets/{id} → detail (with messages)
 *   - POST /support/tickets/{id}/messages → reply
 *   - POST /support/tickets/{id}/close → close
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LifeBuoy,
  Plus,
  RefreshCw,
  Send,
  Ticket,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type {
  SupportTicket,
  SupportTicketDetail,
  SupportTicketPriority,
  SupportTicketStatus,
} from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { NativeSelect as Select } from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn, formatDateTime, timeAgo } from "@/lib/utils";

function statusVariant(s: SupportTicketStatus) {
  switch (s) {
    case "open":
      return "warning" as const;
    case "pending":
      return "secondary" as const;
    case "resolved":
      return "success" as const;
    case "closed":
      return "outline" as const;
    default:
      return "secondary" as const;
  }
}

function priorityVariant(p: SupportTicketPriority) {
  switch (p) {
    case "urgent":
      return "destructive" as const;
    case "high":
      return "warning" as const;
    case "normal":
      return "secondary" as const;
    case "low":
      return "outline" as const;
    default:
      return "secondary" as const;
  }
}

const STATUS_FILTERS: ("all" | SupportTicketStatus)[] = [
  "all",
  "open",
  "pending",
  "resolved",
  "closed",
];

const CATEGORY_OPTIONS = [
  "Billing",
  "Technical",
  "Account",
  "Feature Request",
  "Bug",
  "Other",
];

const PRIORITY_OPTIONS: SupportTicketPriority[] = ["low", "normal", "high", "urgent"];

const MOCK_TICKETS: SupportTicket[] = [
  {
    id: "t-1",
    subject: "Reply auto-pilot stuck on a thread",
    category: "Technical",
    priority: "high",
    status: "open",
    created_at: "2025-02-10T12:00:00Z",
    updated_at: "2025-02-12T09:30:00Z",
  },
  {
    id: "t-2",
    subject: "How do I export my prospects?",
    category: "Account",
    priority: "low",
    status: "resolved",
    created_at: "2025-01-22T08:00:00Z",
    updated_at: "2025-01-22T10:00:00Z",
  },
];

export function SupportPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | SupportTicketStatus>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [replyBody, setReplyBody] = useState("");

  const { data: tickets, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["support", "tickets"],
    queryFn: () => http.get<SupportTicket[]>("/api/v1/support/tickets"),
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["support", "ticket", selectedId],
    queryFn: () =>
      http.get<SupportTicketDetail>(`/api/v1/support/tickets/${selectedId}`),
    enabled: !!selectedId,
  });

  const filtered = (tickets ?? MOCK_TICKETS).filter(
    (t) => statusFilter === "all" || t.status === statusFilter,
  );

  const replyMutation = useMutation({
    mutationFn: (body: string) =>
      http.post(`/api/v1/support/tickets/${selectedId}/messages`, { body }),
    onSuccess: () => {
      toast.success("Reply sent");
      setReplyBody("");
      queryClient.invalidateQueries({
        queryKey: ["support", "ticket", selectedId],
      });
      queryClient.invalidateQueries({ queryKey: ["support", "tickets"] });
    },
    onError: () => toast.error("Failed to send reply"),
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      http.post(`/api/v1/support/tickets/${selectedId}/close`),
    onSuccess: () => {
      toast.success("Ticket closed");
      queryClient.invalidateQueries({
        queryKey: ["support", "ticket", selectedId],
      });
      queryClient.invalidateQueries({ queryKey: ["support", "tickets"] });
    },
    onError: () => toast.error("Failed to close ticket"),
  });

  function handleReply(e: FormEvent) {
    e.preventDefault();
    if (!replyBody.trim()) return toast.error("Reply cannot be empty");
    replyMutation.mutate(replyBody.trim());
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Support"
        description="Open and manage support tickets. Our team typically responds within 4 business hours."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              New ticket
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Ticket list */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Ticket className="h-4 w-4" />
              Tickets
            </CardTitle>
            <div className="flex flex-wrap gap-1 pt-2">
              {STATUS_FILTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs font-medium capitalize transition-colors",
                    statusFilter === s
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-accent",
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={<LifeBuoy className="h-6 w-6" />}
                title="No tickets"
                description="Open a new ticket to get help."
                className="m-4"
              />
            ) : (
              <ul className="divide-y">
                {filtered.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => setSelectedId(t.id)}
                      className={cn(
                        "flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-accent",
                        selectedId === t.id && "bg-accent",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium line-clamp-1">
                          {t.subject}
                        </p>
                        <Badge variant={statusVariant(t.status)}>{t.status}</Badge>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant={priorityVariant(t.priority)} className="text-[10px]">
                          {t.priority}
                        </Badge>
                        <span>·</span>
                        <span>{t.category}</span>
                        <span>·</span>
                        <span>{timeAgo(t.updated_at)}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Ticket detail */}
        <Card className="lg:col-span-2">
          {!selectedId ? (
            <CardContent>
              <EmptyState
                icon={<LifeBuoy className="h-6 w-6" />}
                title="No ticket selected"
                description="Pick a ticket from the list, or open a new one."
              />
            </CardContent>
          ) : detailLoading ? (
            <CardContent className="space-y-3">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-24 w-full" />
            </CardContent>
          ) : detail ? (
            <>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-lg">{detail.subject}</CardTitle>
                    <CardDescription>
                      {detail.category} · opened {timeAgo(detail.created_at)}
                    </CardDescription>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant={statusVariant(detail.status)}>
                      {detail.status}
                    </Badge>
                    <Badge variant={priorityVariant(detail.priority)}>
                      {detail.priority}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Messages thread */}
                <div className="max-h-[28rem] space-y-3 overflow-y-auto rounded-md border bg-muted/30 p-4">
                  {detail.messages.length === 0 ? (
                    <p className="text-center text-sm text-muted-foreground">
                      No messages yet.
                    </p>
                  ) : (
                    detail.messages.map((m) => (
                      <div
                        key={m.id}
                        className={cn(
                          "max-w-[85%] rounded-md p-3 text-sm",
                          m.is_internal_note
                            ? "bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
                            : "bg-background shadow-sm",
                        )}
                      >
                        <div className="mb-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                          <span className="font-medium">
                            {m.author_role ?? "user"}
                            {m.is_internal_note && " · internal note"}
                          </span>
                          <span>{formatDateTime(m.created_at)}</span>
                        </div>
                        <p className="whitespace-pre-wrap">{m.body}</p>
                      </div>
                    ))
                  )}
                </div>

                {/* Reply box (hidden if closed) */}
                {detail.status !== "closed" ? (
                  <form onSubmit={handleReply} className="space-y-2">
                    <Label htmlFor="reply">Reply</Label>
                    <Textarea
                      id="reply"
                      value={replyBody}
                      onChange={(e) => setReplyBody(e.target.value)}
                      placeholder="Type your reply…"
                      rows={3}
                    />
                    <div className="flex items-center justify-between">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => closeMutation.mutate()}
                        disabled={closeMutation.isPending}
                        className="text-red-700 hover:bg-red-50 hover:text-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
                      >
                        <XCircle className="h-4 w-4" />
                        Close ticket
                      </Button>
                      <Button
                        type="submit"
                        size="sm"
                        disabled={replyMutation.isPending || !replyBody.trim()}
                      >
                        <Send className="h-4 w-4" />
                        Send reply
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="rounded-md border bg-muted/50 p-3 text-sm text-muted-foreground">
                    This ticket is closed.{" "}
                    <button
                      className="font-medium text-foreground underline"
                      onClick={() => setCreateOpen(true)}
                    >
                      Open a new ticket
                    </button>{" "}
                    if you need more help.
                  </div>
                )}
              </CardContent>
            </>
          ) : null}
        </Card>
      </div>

      {/* Create ticket dialog */}
      <CreateTicketDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => {
          setSelectedId(id);
          queryClient.invalidateQueries({ queryKey: ["support", "tickets"] });
        }}
      />
    </div>
  );
}

function CreateTicketDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState("");
  const [category, setCategory] = useState(CATEGORY_OPTIONS[0]);
  const [priority, setPriority] = useState<SupportTicketPriority>("normal");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      http.post<SupportTicket>("/api/v1/support/tickets", {
        subject: subject.trim(),
        category,
        priority,
        description: description.trim(),
      }),
    onSuccess: (t) => {
      queryClient.invalidateQueries({ queryKey: ["support-tickets"] });
      toast.success("Ticket created");
      onCreated(t.id);
      onOpenChange(false);
      setSubject("");
      setCategory(CATEGORY_OPTIONS[0]);
      setPriority("normal");
      setDescription("");
    },
    onError: () => toast.error("Failed to create ticket"),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !description.trim()) {
      toast.error("Subject and description are required");
      return;
    }
    mutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <DialogTitle>Open a support ticket</DialogTitle>
        <DialogDescription>
          Tell us what's going on. We'll route it to the right team.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="t-subject">Subject *</Label>
          <Input
            id="t-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Brief summary of your issue"
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="t-category">Category</Label>
            <Select
              id="t-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="t-priority">Priority</Label>
            <Select
              id="t-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as SupportTicketPriority)}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p} className="capitalize">{p}</option>
              ))}
            </Select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="t-desc">Description *</Label>
          <Textarea
            id="t-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Provide as much detail as you can — URLs, error messages, steps to reproduce."
            rows={5}
            required
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            Submit ticket
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
