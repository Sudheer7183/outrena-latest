// /**
//  * CampaignDetailPage.tsx — 5-tab campaign detail (PRD §F-E3 UX spec).
//  *
//  * Tabs: Overview | Cadence | Prospects | Sequences | Analytics
//  * Accessed via /outreach/campaigns/:id
//  */
// import { useState } from "react";
// import { useParams, useNavigate, Link } from "react-router-dom";
// import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
// import {
//   ArrowLeft, Rocket, Pause, Play, Loader2,
//   Calendar, Users2, ListChecks, BarChart3, Settings2, Sparkles
// } from "lucide-react";
// import { toast } from "sonner";
// import { http } from "@/services/apiClient";
// import type { Campaign, Sequence } from "@/types/common";
// import { Button } from "@/components/ui/button";
// import { Badge } from "@/components/ui/badge";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
// import { Skeleton } from "@/components/ui/skeleton";
// import { EmptyState } from "@/components/ui/empty-state";
// import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
// import { formatDate, cn } from "@/lib/utils";

// const STATUS_COLORS: Record<string, string> = {
//   active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
//   draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
//   paused: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
//   completed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
//   archived: "bg-slate-100 text-slate-500",
// };

// const CADENCE_DAYS = [0, 2, 4, 7, 11, 14, 18];
// const CADENCE_LABELS = [
//   "Cold intro", "Value bomb", "Social proof", "Soft ask",
//   "Breakup", "LinkedIn connect", "Final breakup",
// ];

// export function CampaignDetailPage() {
//   const { id } = useParams<{ id: string }>();
//   const navigate = useNavigate();
//   const qc = useQueryClient();
//   const [tab, setTab] = useState("overview");

//   const { data: campaign, isLoading } = useQuery<Campaign>({
//     queryKey: ["campaign", id],
//     queryFn: () => http.get(`/api/v1/campaigns/${id}`),
//     enabled: !!id,
//   });

//   const { data: sequences } = useQuery<{ items: Sequence[]; total: number }>({
//     queryKey: ["sequences", id],
//     queryFn: () => http.get("/api/v1/sequences", { campaign_id: id, limit: 100 }),
//     enabled: !!id && tab === "sequences",
//   });

//   const generateMutation = useMutation({
//     mutationFn: () => http.post(`/api/v1/campaigns/${id}/generate-sequences`),
//     onSuccess: (data: any) => {
//       toast.success(`Generated ${data.created} sequences for ${data.prospects} prospect(s)`);
//       qc.invalidateQueries({ queryKey: ["sequences", id] });
//     },
//     onError: () => toast.error("Failed to generate sequences"),
//   });

//   const statusMutation = useMutation({
//     mutationFn: (newStatus: string) =>
//       http.put(`/api/v1/campaigns/${id}`, { status: newStatus }),
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["campaign", id] });
//       toast.success("Campaign updated");
//     },
//   });

//   if (isLoading) return (
//     <div className="p-6 space-y-4">
//       <Skeleton className="h-8 w-64" />
//       <Skeleton className="h-48 w-full" />
//     </div>
//   );

//   if (!campaign) return (
//     <div className="p-6">
//       <EmptyState title="Campaign not found" description="This campaign may have been deleted." />
//     </div>
//   );

//   return (
//     <div className="flex flex-col gap-6 p-6">
//       {/* Header */}
//       <div className="flex items-start gap-4">
//         <Button variant="ghost" size="icon" onClick={() => navigate("/outreach/campaigns")}>
//           <ArrowLeft className="h-4 w-4" />
//         </Button>
//         <div className="flex-1 min-w-0">
//           <div className="flex items-center gap-3 flex-wrap">
//             <h1 className="text-2xl font-bold tracking-tight truncate">{campaign.name}</h1>
//             <Badge className={cn("text-xs", STATUS_COLORS[campaign.status] ?? "")}>
//               {campaign.status}
//             </Badge>
//           </div>
//           <p className="text-sm text-muted-foreground mt-1">
//             Framework: {campaign.framework ?? "—"} · Owner: {campaign.ownerUserId ?? "—"}
//           </p>
//         </div>
//         <div className="flex gap-2 shrink-0">
//           {campaign.status === "active" && (
//             <Button variant="outline" size="sm" onClick={() => statusMutation.mutate("paused")}>
//               <Pause className="h-3.5 w-3.5 mr-1" /> Pause
//             </Button>
//           )}
//           {campaign.status === "paused" && (
//             <Button variant="outline" size="sm" onClick={() => statusMutation.mutate("active")}>
//               <Play className="h-3.5 w-3.5 mr-1" /> Resume
//             </Button>
//           )}
//           {campaign.status === "draft" && (
//             <Button size="sm" onClick={() => statusMutation.mutate("active")}>
//               <Rocket className="h-3.5 w-3.5 mr-1" /> Activate
//             </Button>
//           )}
//         </div>
//       </div>

//       {/* Tabs */}
//       <Tabs value={tab} onValueChange={setTab}>
//         <TabsList>
//           <TabsTrigger value="overview"><Settings2 className="h-3.5 w-3.5 mr-1.5" />Overview</TabsTrigger>
//           <TabsTrigger value="cadence"><Calendar className="h-3.5 w-3.5 mr-1.5" />Cadence</TabsTrigger>
//           <TabsTrigger value="prospects"><Users2 className="h-3.5 w-3.5 mr-1.5" />Prospects</TabsTrigger>
//           <TabsTrigger value="sequences"><ListChecks className="h-3.5 w-3.5 mr-1.5" />Sequences</TabsTrigger>
//           <TabsTrigger value="analytics"><BarChart3 className="h-3.5 w-3.5 mr-1.5" />Analytics</TabsTrigger>
//         </TabsList>

//         {/* Overview */}
//         <TabsContent value="overview" className="mt-4">
//           <div className="grid gap-4 md:grid-cols-2">
//             <Card>
//               <CardHeader><CardTitle className="text-sm">Campaign Settings</CardTitle></CardHeader>
//               <CardContent className="space-y-2 text-sm">
//                 {[
//                   ["Status", campaign.status],
//                   ["Framework", campaign.framework ?? "—"],
//                   ["ICP Profile", (campaign as any).icpProfileId ?? "—"],
//                   ["Domain", (campaign as any).domainId ?? "—"],
//                   ["Created", formatDate(campaign.createdAt)],
//                   ["Updated", formatDate(campaign.updatedAt)],
//                 ].map(([k, v]) => (
//                   <div key={k} className="flex justify-between">
//                     <span className="text-muted-foreground">{k}</span>
//                     <span className="font-medium">{v}</span>
//                   </div>
//                 ))}
//               </CardContent>
//             </Card>
//             <Card>
//               <CardHeader><CardTitle className="text-sm">GTM Thesis</CardTitle></CardHeader>
//               <CardContent>
//                 <p className="text-sm text-muted-foreground">
//                   {(campaign as any).gtmThesis || "No GTM thesis set. Use Email Studio to generate one."}
//                 </p>
//               </CardContent>
//             </Card>
//           </div>
//         </TabsContent>

//         {/* Cadence */}
//         <TabsContent value="cadence" className="mt-4">
//           <Card>
//             <CardHeader>
//               <CardTitle>7-Touch Cadence</CardTitle>
//               <CardDescription>Default outreach cadence. Each touch auto-generates a sequence when a prospect is linked.</CardDescription>
//             </CardHeader>
//             <CardContent>
//               <div className="relative">
//                 {/* Timeline line */}
//                 <div className="absolute left-6 top-4 bottom-4 w-px bg-border" />
//                 <div className="space-y-4">
//                   {CADENCE_DAYS.map((day, i) => (
//                     <div key={i} className="flex items-start gap-4 pl-14 relative">
//                       <div className="absolute left-4 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-bold">
//                         {i + 1}
//                       </div>
//                       <div className="flex-1">
//                         <div className="flex items-center gap-2">
//                           <Badge variant="outline" className="text-xs">Day {day}</Badge>
//                           <span className="text-sm font-medium">{CADENCE_LABELS[i]}</span>
//                         </div>
//                       </div>
//                     </div>
//                   ))}
//                 </div>
//               </div>
//             </CardContent>
//           </Card>
//         </TabsContent>

//         {/* Prospects */}
//         <TabsContent value="prospects" className="mt-4">
//           <Card>
//             <CardHeader>
//               <CardTitle>Linked Prospects</CardTitle>
//               <CardDescription>
//                 Prospects enrolled in this campaign. Add prospects via the{" "}
//                 <Link to="/prospects" className="underline">Prospects</Link> page.
//               </CardDescription>
//             </CardHeader>
//             <CardContent>
//               <p className="text-sm text-muted-foreground">
//                 Use the Prospects page to search, filter, and bulk-link prospects to this campaign.
//               </p>
//             </CardContent>
//           </Card>
//         </TabsContent>

//         {/* Sequences */}
//         <TabsContent value="sequences" className="mt-4">
//           <Card>
//             <CardHeader>
//               <div className="flex items-center justify-between">
//                 <div>
//                   <CardTitle>Sequences</CardTitle>
//                   <CardDescription>Per-prospect execution of the 7-touch cadence.</CardDescription>
//                 </div>
//                 <Button
//                   size="sm"
//                   variant="outline"
//                   onClick={() => generateMutation.mutate()}
//                   disabled={generateMutation.isPending}
//                 >
//                   {generateMutation.isPending
//                     ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Generating…</>
//                     : <><Sparkles className="h-3.5 w-3.5 mr-1" />Generate All Sequences</>}
//                 </Button>
//               </div>
//             </CardHeader>
//             <CardContent>
//               {!sequences?.items?.length
//                 ? <EmptyState title="No sequences yet" description="Click Generate All Sequences to auto-create the 7-touch cadence for each linked prospect." />
//                 : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead>Prospect</TableHead>
//                         <TableHead>Touch</TableHead>
//                         <TableHead>Status</TableHead>
//                         <TableHead>Scheduled</TableHead>
//                         <TableHead>Sent</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {(Array.isArray(sequences.items) ? sequences.items : []).map((s) => (
//                         <TableRow key={s.id}>
//                           <TableCell className="text-xs font-mono">{s.prospectId?.slice(0, 8)}…</TableCell>
//                           <TableCell>{(s as any).touchNumber ?? "—"}</TableCell>
//                           <TableCell><Badge variant="outline" className="text-xs">{s.status}</Badge></TableCell>
//                           <TableCell className="text-xs">{formatDate((s as any).scheduledFor)}</TableCell>
//                           <TableCell className="text-xs">{formatDate((s as any).sentAt)}</TableCell>
//                         </TableRow>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//             </CardContent>
//           </Card>
//         </TabsContent>

//         {/* Analytics */}
//         <TabsContent value="analytics" className="mt-4">
//           <Card>
//             <CardHeader>
//               <CardTitle>Campaign Analytics</CardTitle>
//             </CardHeader>
//             <CardContent>
//               <p className="text-sm text-muted-foreground">
//                 View full analytics on the{" "}
//                 <Link to="/optimize/analytics" className="underline">Analytics page</Link>{" "}
//                 — filter by this campaign ID: <code className="bg-muted px-1 rounded text-xs">{id}</code>
//               </p>
//             </CardContent>
//           </Card>
//         </TabsContent>
//       </Tabs>
//     </div>
//   );
// }

/**
 * CampaignDetailPage.tsx — 5-tab campaign detail (PRD §F-E3 UX spec).
 *
 * Tabs: Overview | Cadence | Prospects | Sequences | Analytics
 * Accessed via /outreach/campaigns/:id
 */
import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Rocket, Pause, Play, Loader2,
  Calendar, Users2, ListChecks, BarChart3, Settings2, Sparkles,
  Mail, ShieldCheck
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { Campaign, Sequence } from "@/types/common";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  paused: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  completed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  archived: "bg-slate-100 text-slate-500",
};

const CADENCE_DAYS = [0, 2, 4, 7, 11, 14, 18];
const CADENCE_LABELS = [
  "Cold intro", "Value bomb", "Social proof", "Soft ask",
  "Breakup", "LinkedIn connect", "Final breakup",
];

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState("overview");

  const { data: campaign, isLoading } = useQuery<Campaign>({
    queryKey: ["campaign", id],
    queryFn: () => http.get(`/api/v1/campaigns/${id}`),
    enabled: !!id,
  });

  const { data: sequences } = useQuery<{ items: Sequence[]; total: number }>({
    queryKey: ["sequences", id],
    queryFn: () => http.get("/api/v1/sequences", { campaign_id: id, limit: 100 }),
    enabled: !!id && tab === "sequences",
  });

  const generateMutation = useMutation({
    mutationFn: () => http.post(`/api/v1/campaigns/${id}/generate-sequences`),
    onSuccess: (data: any) => {
      toast.success(`Generated ${data.created} sequences for ${data.prospects} prospect(s)`);
      qc.invalidateQueries({ queryKey: ["sequences", id] });
    },
    onError: () => toast.error("Failed to generate sequences"),
  });

  const statusMutation = useMutation({
    mutationFn: (newStatus: string) =>
      http.put(`/api/v1/campaigns/${id}`, { status: newStatus }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaign", id] });
      toast.success("Campaign updated");
    },
  });

  if (isLoading) return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-48 w-full" />
    </div>
  );

  if (!campaign) return (
    <div className="p-6">
      <EmptyState title="Campaign not found" description="This campaign may have been deleted." />
    </div>
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/outreach/campaigns")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight truncate">{campaign.name}</h1>
            <Badge className={cn("text-xs", STATUS_COLORS[campaign.status] ?? "")}>
              {campaign.status}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Framework: {campaign.framework ?? "—"} · Owner: {campaign.ownerUserId ?? "—"}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {campaign.status === "active" && (
            <Button variant="outline" size="sm" onClick={() => statusMutation.mutate("paused")}>
              <Pause className="h-3.5 w-3.5 mr-1" /> Pause
            </Button>
          )}
          {campaign.status === "paused" && (
            <Button variant="outline" size="sm" onClick={() => statusMutation.mutate("active")}>
              <Play className="h-3.5 w-3.5 mr-1" /> Resume
            </Button>
          )}
          {campaign.status === "draft" && (
            <Button size="sm" onClick={() => statusMutation.mutate("active")}>
              <Rocket className="h-3.5 w-3.5 mr-1" /> Activate
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview"><Settings2 className="h-3.5 w-3.5 mr-1.5" />Overview</TabsTrigger>
          <TabsTrigger value="cadence"><Calendar className="h-3.5 w-3.5 mr-1.5" />Cadence</TabsTrigger>
          <TabsTrigger value="prospects"><Users2 className="h-3.5 w-3.5 mr-1.5" />Prospects</TabsTrigger>
          <TabsTrigger value="sequences"><ListChecks className="h-3.5 w-3.5 mr-1.5" />Sequences</TabsTrigger>
          <TabsTrigger value="analytics"><BarChart3 className="h-3.5 w-3.5 mr-1.5" />Analytics</TabsTrigger>
          <TabsTrigger value="sending"><Mail className="h-3.5 w-3.5 mr-1.5" />Email Sending</TabsTrigger>
          <TabsTrigger value="compliance"><ShieldCheck className="h-3.5 w-3.5 mr-1.5" />Compliance</TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-sm">Campaign Settings</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                {[
                  ["Status", campaign.status],
                  ["Framework", campaign.framework ?? "—"],
                  ["ICP Profile", (campaign as any).icpProfileId ?? "—"],
                  ["Domain", (campaign as any).domainId ?? "—"],
                  ["Created", formatDate(campaign.createdAt)],
                  ["Updated", formatDate(campaign.updatedAt)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-muted-foreground">{k}</span>
                    <span className="font-medium">{v}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-sm">GTM Thesis</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {(campaign as any).gtmThesis || "No GTM thesis set. Use Email Studio to generate one."}
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Cadence */}
        <TabsContent value="cadence" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>7-Touch Cadence</CardTitle>
              <CardDescription>Default outreach cadence. Each touch auto-generates a sequence when a prospect is linked.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative">
                {/* Timeline line */}
                <div className="absolute left-6 top-4 bottom-4 w-px bg-border" />
                <div className="space-y-4">
                  {CADENCE_DAYS.map((day, i) => (
                    <div key={i} className="flex items-start gap-4 pl-14 relative">
                      <div className="absolute left-4 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-bold">
                        {i + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">Day {day}</Badge>
                          <span className="text-sm font-medium">{CADENCE_LABELS[i]}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Prospects */}
        <TabsContent value="prospects" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Linked Prospects</CardTitle>
              <CardDescription>
                Prospects enrolled in this campaign. Add prospects via the{" "}
                <Link to="/prospects" className="underline">Prospects</Link> page.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Use the Prospects page to search, filter, and bulk-link prospects to this campaign.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sequences */}
        <TabsContent value="sequences" className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Sequences</CardTitle>
                  <CardDescription>Per-prospect execution of the 7-touch cadence.</CardDescription>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  {generateMutation.isPending
                    ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Generating…</>
                    : <><Sparkles className="h-3.5 w-3.5 mr-1" />Generate All Sequences</>}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!sequences?.items?.length
                ? <EmptyState title="No sequences yet" description="Click Generate All Sequences to auto-create the 7-touch cadence for each linked prospect." />
                : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Prospect</TableHead>
                        <TableHead>Touch</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Scheduled</TableHead>
                        <TableHead>Sent</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(Array.isArray(sequences.items) ? sequences.items : []).map((s) => (
                        <TableRow key={s.id}>
                          <TableCell className="text-xs font-mono">{s.prospectId?.slice(0, 8)}…</TableCell>
                          <TableCell>{(s as any).touchNumber ?? "—"}</TableCell>
                          <TableCell><Badge variant="outline" className="text-xs">{s.status}</Badge></TableCell>
                          <TableCell className="text-xs">{formatDate((s as any).scheduledFor)}</TableCell>
                          <TableCell className="text-xs">{formatDate((s as any).sentAt)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analytics */}
        <TabsContent value="analytics" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Analytics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                View full analytics on the{" "}
                <Link to="/optimize/analytics" className="underline">Analytics page</Link>{" "}
                — filter by this campaign ID: <code className="bg-muted px-1 rounded text-xs">{id}</code>
              </p>
            </CardContent>
          </Card>
        </TabsContent>
        {/* Email Sending tab */}
        <TabsContent value="sending" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Email Sending (MailBridge)</CardTitle>
              <CardDescription className="text-xs">
                Configure MailBridge SMTP/API connections for this campaign.
                Manage connections in <Link to="/setup/mailbridge" className="underline">Setup → MailBridge</Link>.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                MailBridge settings are managed at the campaign level from the{" "}
                <button
                  className="underline text-foreground"
                  onClick={() => navigate("/outreach/campaigns")}
                >
                  Campaigns list view
                </button>{" "}
                — open this campaign's detail panel and switch to the Email Sending tab.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Compliance tab */}
        <TabsContent value="compliance" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Compliance</CardTitle>
              <CardDescription className="text-xs">
                CAN-SPAM / GDPR footer, unsubscribe URL, and webhook settings.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {[
                ["Sender Name",      (campaign as any)?.senderName      ?? "—"],
                ["Sender Email",     (campaign as any)?.senderEmail     ?? "—"],
                ["Physical Address", (campaign as any)?.physicalAddress  ?? "Not set"],
                ["Unsubscribe URL",  (campaign as any)?.unsubscribeUrl   ?? "Not set"],
              ].map(([label, value]) => (
                <div key={label as string} className="flex justify-between gap-4">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium text-right">{value}</span>
                </div>
              ))}
              <p className="text-xs text-muted-foreground pt-2">
                Edit compliance settings from the Campaigns list → campaign detail panel → Compliance tab.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}