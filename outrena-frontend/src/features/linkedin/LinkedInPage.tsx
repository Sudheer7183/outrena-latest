/**
 * LinkedInPage.tsx — LinkedIn config + engagement + inbox.
 *
 * Tabs:
 *  - Config: list of LinkedIn accounts (accountName, masked cookies/session,
 *    isActive, dailyLimit) + add dialog.
 *  - Engagement: list of engagement tasks (prospect, action, status,
 *    scheduledAt) + create dialog.
 *  - Inbox: list of inbox messages (from, preview, receivedAt, triaged) +
 *    triage button → toast.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Linkedin,
  Plus,
  Pencil,
  Trash2,
  MessageSquare,
  UserPlus,
  Heart,
  Inbox as InboxIcon,
  Info,
  Loader2,
  Save,
  Sparkles,
  Send,
  Clock,
  Target,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDateTime, timeAgo, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/* ── Types ─────────────────────────────────────────────────────────── */

interface LinkedInAccount {
  id: string;
  accountName: string;
  session_cookie: string | null;
  isActive: boolean;
  daily_limit: number | null;
  used_today: number | null;
}

type EngagementAction = "connect" | "message" | "comment";
type EngagementStatus = "pending" | "scheduled" | "done" | "failed";

interface EngagementTask {
  id: string;
  prospectId: string | null;
  prospectName?: string; // display only (from mock or joined)
  prospectCompany?: string; // display only (from mock or joined)
  action: EngagementAction;
  status: EngagementStatus;
  scheduledAt: string | null;
  note: string | null;
  message?: string | null; // legacy alias, prefer note
}

interface InboxMessage {
  id: string;
  fromName: string;
  fromTitle: string;
  preview: string;
  receivedAt: string;
  triaged: boolean;
  category: string | null;
}

/* ── ICP Check types ───────────────────────────────────────────────── */

interface IcpMatch {
  prospectName: string;
  icpProfileMatched: string;
  matchReason: string;
  suggestedConnectionNote: string;
}

interface IcpCheckResult {
  checked: number;
  matchesFound: number;
  matches: IcpMatch[];
}

/* ── Mock data ─────────────────────────────────────────────────────── */

const MOCK_ACCOUNTS: LinkedInAccount[] = [
  { id: "a1", accountName: "alex@outrena.io", session_cookie: "li_at=••••3F9a", isActive: true, daily_limit: 80, used_today: 32 },
  { id: "a2", accountName: "sdr-team@outrena.io", session_cookie: "li_at=••••b21Z", isActive: true, daily_limit: 60, used_today: 60 },
  { id: "a3", accountName: "events@outrena.io", session_cookie: "li_at=••••8c4d", isActive: false, daily_limit: 40, used_today: 0 },
];

const MOCK_ENGAGEMENTS: EngagementTask[] = [
  mkE("e1", "p1", "Priya Shankar", "Ledgerline", "connect", "scheduled", "2025-01-12T10:00:00Z", null),
  mkE("e2", "p2", "Marcus Reuel", "Vaultnode", "message", "pending", null, "Hi Marcus — saw your post on SDR ramp…"),
  mkE("e3", "p3", "Elena Voss", "Northbridge Pay", "comment", "done", "2025-01-09T14:30:00Z", "Great post on Series B scaling!"),
  mkE("e4", "p4", "Daniel Okoro", "SwiftForge", "connect", "done", "2025-01-08T09:15:00Z", null),
  mkE("e5", "p5", "Sara Lindqvist", "Blue Harbor", "message", "failed", "2025-01-10T11:00:00Z", "Hi Sara — quick question on your HR Ops stack…"),
];

const MOCK_INBOX: InboxMessage[] = [
  mkI("m1", "Priya Shankar", "VP Sales @ Ledgerline", "Thanks for reaching out! We're actually evaluating tools in this space. Do you have time next Tuesday?", "2025-01-11T16:30:00Z", false, null),
  mkI("m2", "Marcus Reuel", "VP RevOps @ Vaultnode", "Hey Alex — interesting. Can you send me a one-pager?", "2025-01-11T12:15:00Z", false, null),
  mkI("m3", "Elena Voss", "Head of Sales @ Northbridge Pay", "Not the right time, but please follow up in Q2.", "2025-01-10T18:45:00Z", true, "follow-up"),
  mkI("m4", "Daniel Okoro", "Director of Eng @ SwiftForge", "Out of office until Jan 20.", "2025-01-09T08:00:00Z", true, "ooo"),
  mkI("m5", "Sara Lindqvist", "Head of People Ops @ Blue Harbor", "Who else should I loop in from my team?", "2025-01-08T14:20:00Z", false, null),
];

function mkE(
  id: string,
  prospectId: string,
  prospectName: string,
  prospectCompany: string,
  action: EngagementAction,
  status: EngagementStatus,
  scheduledAt: string | null,
  note: string | null,
): EngagementTask {
  return { id, prospectId, prospectName, prospectCompany, action, status, scheduledAt, note };
}

function mkI(
  id: string,
  fromName: string,
  fromTitle: string,
  preview: string,
  receivedAt: string,
  triaged: boolean,
  category: string | null,
): InboxMessage {
  return { id, fromName, fromTitle, preview, receivedAt, triaged, category };
}

const ACTION_META: Record<EngagementAction, { label: string; icon: typeof UserPlus; variant: "default" | "secondary" | "outline" }> = {
  connect: { label: "Connect", icon: UserPlus, variant: "default" },
  message: { label: "Message", icon: MessageSquare, variant: "secondary" },
  comment: { label: "Comment", icon: Heart, variant: "outline" },
};

const STATUS_VARIANT: Record<EngagementStatus, "default" | "secondary" | "success" | "destructive" | "warning"> = {
  pending: "secondary",
  scheduled: "warning",
  done: "success",
  failed: "destructive",
};

/* ── Page ──────────────────────────────────────────────────────────── */

export function LinkedInPage() {
  const [tab, setTab] = useState("config");

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="LinkedIn"
        description="Manage LinkedIn accounts, schedule engagement tasks, and triage inbox replies."
      />

      <Alert variant="default">
        <Info className="h-4 w-4" />
        <AlertTitle>Companion channel — runs in parallel to email outreach</AlertTitle>
        <AlertDescription>
          LinkedIn engagement is a separate channel from email Campaigns &amp;
          Sequences. Use it to layer connection requests, messages, and likes on
          top of an email sequence for the same prospect. Daily limits are
          per-account and enforced client-side to keep your sessions safe —
          OUTRENA does not auto-sync LinkedIn replies back to email reply
          drafting (triage them manually in the Inbox tab).
        </AlertDescription>
      </Alert>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="config">
            <Linkedin className="mr-1.5 h-4 w-4" />
            Config
          </TabsTrigger>
          <TabsTrigger value="engagement">
            <Send className="mr-1.5 h-4 w-4" />
            Engagement
          </TabsTrigger>
          <TabsTrigger value="inbox">
            <InboxIcon className="mr-1.5 h-4 w-4" />
            Inbox
          </TabsTrigger>
        </TabsList>

        <TabsContent value="config">
          <ConfigTab />
        </TabsContent>
        <TabsContent value="engagement">
          <EngagementTab />
        </TabsContent>
        <TabsContent value="inbox">
          <InboxTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Config tab ────────────────────────────────────────────────────── */

function ConfigTab() {
  const qc = useQueryClient();
  const [edit, setEdit] = useState<LinkedInAccount | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<LinkedInAccount | null>(null);

  const query = useQuery<LinkedInAccount[]>({
    queryKey: ["linkedin-config"],
    queryFn: () => http.get<LinkedInAccount[]>("/api/v1/linkedin/config"),
  });
  const accounts = query.data ?? MOCK_ACCOUNTS;

  const saveMutation = useMutation({
    mutationFn: (acc: LinkedInAccount) => {
      if (accounts.some((a) => a.id === acc.id)) {
        return http.put(`/api/v1/linkedin/config/${acc.id}`, acc);
      }
      return http.post("/api/v1/linkedin/config", acc);
    },
    onSuccess: () => {
      toast.success("Account saved");
      setEdit(null);
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["linkedin-config"] });
    },
    onError: () => toast.error("Save failed — backend unavailable"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/linkedin/config/${id}`),
    onSuccess: () => {
      toast.success("Account deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["linkedin-config"] });
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">LinkedIn Accounts</CardTitle>
            <CardDescription>Authenticated sessions used for engagement + inbox.</CardDescription>
          </div>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Account
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {query.isError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <p className="text-sm font-medium">Failed to load LinkedIn accounts</p>
            <Button variant="outline" onClick={() => query.refetch()}>
              Retry
            </Button>
          </div>
        ) : query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Account</TableHead>
              <TableHead>Session</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Today / Limit</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {accounts.map((acc) => (
              <TableRow key={acc.id}>
                <TableCell className="font-medium">{acc.accountName}</TableCell>
                <TableCell>
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{acc.session_cookie ?? "—"}</code>
                </TableCell>
                <TableCell>
                  <Badge variant={acc.isActive ? "success" : "secondary"}>
                    {acc.isActive ? "Active" : "Paused"}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {acc.used_today ?? 0} / {acc.daily_limit ?? "—"}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button size="icon" variant="ghost" aria-label="Edit" onClick={() => setEdit(acc)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Edit account</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Delete"
                          onClick={() => setDeleteTarget(acc)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete account</TooltipContent>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        )}
      </CardContent>

      <AccountDialog
        open={!!edit || addOpen}
        account={edit}
        onClose={() => {
          setEdit(null);
          setAddOpen(false);
        }}
        onSubmit={(acc) => saveMutation.mutate(acc)}
        isPending={saveMutation.isPending}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete LinkedIn account?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.accountName
              ? `Account "${deleteTarget.accountName}" and its stored session will be permanently removed. Scheduled engagement tasks for this account will be cancelled. This action cannot be undone.`
              : "This LinkedIn account will be permanently removed. This action cannot be undone."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              deleteTarget && deleteMutation.mutate(deleteTarget.id)
            }
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>
    </Card>
  );
}

function AccountDialog({
  open,
  account,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  account: LinkedInAccount | null;
  onClose: () => void;
  onSubmit: (acc: LinkedInAccount) => void;
  isPending: boolean;
}) {
  const [accountName, setAccountName] = useState("");
  const [session, setSession] = useState("");
  const [dailyLimit, setDailyLimit] = useState(80);
  const [isActive, setIsActive] = useState(true);

  useMemo(() => {
    setAccountName(account?.accountName ?? "");
    setSession("");
    setDailyLimit(account?.daily_limit ?? 80);
    setIsActive(account?.isActive ?? true);
  }, [account, open]);

  function submit() {
    if (!accountName.trim()) return;
    onSubmit({
      id: account?.id ?? `a-${Date.now()}`,
      accountName: accountName.trim(),
      session_cookie: session ? maskSession(session) : (account?.session_cookie ?? null),
      isActive,
      daily_limit: dailyLimit,
      used_today: account?.used_today ?? 0,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>{account ? "Edit Account" : "Add Account"}</DialogTitle>
        <DialogDescription>Provide the LinkedIn account email + a session cookie (li_at).</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="acc-name">Account Email</Label>
          <Input id="acc-name" value={accountName} onChange={(e) => setAccountName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="acc-session">
            Session Cookie <span className="text-muted-foreground">(li_at)</span>
          </Label>
          <Input
            id="acc-session"
            type="password"
            placeholder="paste li_at cookie…"
            value={session}
            onChange={(e) => setSession(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <InfoLabel
              htmlFor="acc-limit"
              label="Daily Limit"
              info="Max LinkedIn actions (invites, messages, follows) per UTC day. LinkedIn safely tolerates ~80/day; higher risks account restriction."
            />
            <Input
              id="acc-limit"
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value) || 0)}
            />
          </div>
          <div className="space-y-2">
            <Label>Active</Label>
            <div className="flex h-10 items-center gap-2">
              <Switch checked={isActive} onCheckedChange={setIsActive} />
              <span className="text-sm text-muted-foreground">{isActive ? "Active" : "Paused"}</span>
            </div>
          </div>
        </div>
      </div>
      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button onClick={submit} disabled={isPending || !accountName.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Engagement tab ────────────────────────────────────────────────── */

function EngagementTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [icpResult, setIcpResult] = useState<IcpCheckResult | null>(null);

  const query = useQuery<EngagementTask[]>({
    queryKey: ["linkedin-engagements"],
    queryFn: () => http.get<EngagementTask[]>("/api/v1/linkedin/engagements"),
  });
  const tasks = query.data ?? MOCK_ENGAGEMENTS;

  const createMutation = useMutation({
    mutationFn: (task: Omit<EngagementTask, "id">) =>
      http.post<EngagementTask>("/api/v1/linkedin/engagements", task),
    onSuccess: () => {
      toast.success("Engagement task created");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["linkedin-engagements"] });
    },
    onError: () => toast.error("Create failed — backend unavailable"),
  });

  const icpCheckMut = useMutation({
    mutationFn: () =>
      http.post<IcpCheckResult>("/api/v1/linkedin/engagements/check-icp"),
    onSuccess: (data) => {
      setIcpResult(data);
      toast.success(`ICP check complete: ${data.matchesFound} match(es) found out of ${data.checked} checked`);
    },
    onError: () => toast.error("ICP check failed — backend unavailable"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Engagement Tasks</CardTitle>
            <CardDescription>Scheduled connects, messages, and comments.</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => icpCheckMut.mutate()}
              disabled={icpCheckMut.isPending}
            >
              {icpCheckMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Target className="h-4 w-4" />
              )}
              Check ICP Matches
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              New Task
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Prospect</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Scheduled</TableHead>
              <TableHead>Message</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((t) => {
              const meta = ACTION_META[t.action];
              const Icon = meta.icon;
              return (
                <TableRow key={t.id}>
                  <TableCell>
                    <div className="space-y-0.5">
                      <p className="font-medium">{t.prospectName ?? t.prospectId ?? "—"}</p>
                      <p className="text-xs text-muted-foreground">{t.prospectCompany ?? ""}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={meta.variant} className="gap-1">
                      <Icon className="h-3 w-3" />
                      {meta.label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[t.status]} className="capitalize">
                      {t.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {t.scheduledAt ? (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDateTime(t.scheduledAt)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="max-w-xs text-xs text-muted-foreground">
                    {(t.note ?? t.message) ? truncate((t.note ?? t.message)!, 80) : "—"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>

      <EngagementDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={(task) => createMutation.mutate(task)}
        isPending={createMutation.isPending}
      />

      {/* ICP Match Results */}
      {icpResult && (
        <Card className="mt-4">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">ICP Match Results</CardTitle>
                <CardDescription>
                  {icpResult.checked} checked · {icpResult.matchesFound} matches found
                </CardDescription>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setIcpResult(null)}>
                Dismiss
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {icpResult.matches.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No ICP matches found.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prospect</TableHead>
                    <TableHead>ICP Profile</TableHead>
                    <TableHead>Match Reason</TableHead>
                    <TableHead>Suggested Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {icpResult.matches.map((m, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{m.prospectName}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{m.icpProfileMatched}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {truncate(m.matchReason, 80)}
                      </TableCell>
                      <TableCell className="max-w-xs text-xs text-muted-foreground">
                        {truncate(m.suggestedConnectionNote, 100)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </Card>
  );
}

function EngagementDialog({
  open,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (task: Omit<EngagementTask, "id">) => void;
  isPending: boolean;
}) {
  const [prospectId, setProspectId] = useState("");
  const [prospectName, setProspectName] = useState("");
  const [prospectCompany, setProspectCompany] = useState("");
  const [action, setAction] = useState<EngagementAction>("connect");
  const [scheduledAt, setScheduledAt] = useState("");
  const [note, setNote] = useState("");

  function submit() {
    if (!prospectName.trim()) return;
    onSubmit({
      prospectId: prospectId.trim() || null,
      prospectName: prospectName.trim(),
      prospectCompany: prospectCompany.trim(),
      action,
      status: scheduledAt ? "scheduled" : "pending",
      scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      note: note.trim() || null,
    });
    setProspectId(""); setProspectName(""); setProspectCompany(""); setAction("connect");
    setScheduledAt(""); setNote("");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>New Engagement Task</DialogTitle>
        <DialogDescription>Schedule a connect, message, or comment.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="eng-prospect">Prospect Name</Label>
            <Input id="eng-prospect" value={prospectName} onChange={(e) => setProspectName(e.target.value)} placeholder="e.g. Priya Shankar" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="eng-company">Company</Label>
            <Input id="eng-company" value={prospectCompany} onChange={(e) => setProspectCompany(e.target.value)} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="eng-action">Action</Label>
            <select
              id="eng-action"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={action}
              onChange={(e) => setAction(e.target.value as EngagementAction)}
            >
              <option value="connect">Connect</option>
              <option value="message">Message</option>
              <option value="comment">Comment</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="eng-scheduled">Scheduled At</Label>
            <Input
              id="eng-scheduled"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="eng-note">Note</Label>
          <Textarea
            id="eng-note"
            rows={3}
            placeholder="Hi {firstName} — saw your post…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      </div>
      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button onClick={submit} disabled={isPending || !prospectName.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Create Task
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Inbox tab ─────────────────────────────────────────────────────── */

function InboxTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "untriaged" | "triaged">("all");

  const query = useQuery<InboxMessage[]>({
    queryKey: ["linkedin-inbox"],
    queryFn: () => http.get<InboxMessage[]>("/api/v1/linkedin/inbox"),
  });
  const allMessages = query.data ?? MOCK_INBOX;
  const messages = useMemo(() => {
    if (filter === "untriaged") return allMessages.filter((m) => !m.triaged);
    if (filter === "triaged") return allMessages.filter((m) => m.triaged);
    return allMessages;
  }, [allMessages, filter]);

  const triageMutation = useMutation({
    mutationFn: (id: string) =>
      http.post(`/api/v1/linkedin/inbox/triage`, { messageId: id }),
    onSuccess: () => {
      toast.success("Triage complete", { description: "Reply drafted in Reply Drafts." });
      qc.invalidateQueries({ queryKey: ["linkedin-inbox"] });
    },
    onError: () => toast.error("Triage failed — backend unavailable"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Inbox</CardTitle>
            <CardDescription>Triage inbound LinkedIn messages into reply drafts.</CardDescription>
          </div>
          <div className="flex items-center gap-1 rounded-md border p-0.5">
            {(["all", "untriaged", "triaged"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={cn(
                  "rounded-sm px-3 py-1 text-xs font-medium capitalize transition-colors",
                  filter === f ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {messages.length === 0 ? (
          <EmptyState
            icon={<InboxIcon className="h-6 w-6" />}
            title="No messages"
            description="Inbox is empty for this filter."
          />
        ) : (
          <ul className="divide-y">
            {messages.map((m) => (
              <li key={m.id} className="flex items-start gap-3 p-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                  {m.fromName.slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">{m.fromName}</p>
                    <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(m.receivedAt)}</span>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">{m.fromTitle}</p>
                  <p className="text-sm text-muted-foreground">{truncate(m.preview, 200)}</p>
                  <div className="flex items-center gap-2 pt-1">
                    {m.triaged ? (
                      <>
                        <Badge variant="success">Triaged</Badge>
                        {m.category && <Badge variant="secondary">{m.category}</Badge>}
                      </>
                    ) : (
                      <Badge variant="warning">Needs triage</Badge>
                    )}
                  </div>
                </div>
                {!m.triaged && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={triageMutation.isPending && triageMutation.variables === m.id}
                    onClick={() => triageMutation.mutate(m.id)}
                  >
                    {triageMutation.isPending && triageMutation.variables === m.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    Triage
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Helpers ───────────────────────────────────────────────────────── */

function maskSession(session: string): string {
  if (session.length <= 8) return `${session.slice(0, 3)}••••`;
  return `${session.slice(0, 4)}••••••${session.slice(-4)}`;
}
