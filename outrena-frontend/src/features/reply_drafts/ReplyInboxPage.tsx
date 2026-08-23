// /**
//  * ReplyInboxPage.tsx — Gap closure RI-1 through RI-8
//  * Layout matches Next.js reference: two-tab (Manual Review + Auto-Pilot),
//  * inline toolbar, draft list + detail panel side-by-side, inline deal card.
//  */
// import { useMemo, useState, useEffect } from 'react';
// import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
// import {
//   Bot, CheckCircle2, Send, Sparkles, FileDown, Eye, Info,
//   Loader2, MessageCircleReply, Zap, Ban, DollarSign, Clock,
//   ShieldAlert, XCircle,
// } from 'lucide-react';
// import { toast } from 'sonner';

// import { http } from '@/services/apiClient';
// import { cn } from '@/lib/utils';
// import { Badge } from '@/components/ui/badge';
// import { Button } from '@/components/ui/button';
// import {
//   Card, CardContent, CardDescription, CardHeader, CardTitle,
// } from '@/components/ui/card';
// import {
//   Dialog, DialogContent, DialogDescription, DialogFooter,
//   DialogHeader, DialogTitle,
// } from '@/components/ui/dialog';
// import { Input } from '@/components/ui/input';
// import { Label } from '@/components/ui/label';
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
// import { Switch } from '@/components/ui/switch';
// import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// import { Textarea } from '@/components/ui/textarea';

// // ─── Types ────────────────────────────────────────────────────────────────────

// interface ReplyDraft {
//   id: string;
//   sequenceId: string;
//   prospectId: string;
//   originalReply: string;
//   category: string;
//   summary: string | null;
//   suggestedAction: string | null;
//   draftBody: string | null;
//   status: string;
//   sentAt: string | null;
//   autoPilotEligible: boolean;
//   confidence: number | null;
//   autoSentAt: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// interface AutoPilotPreview {
//   eligible: ReplyDraft[];
//   count: number;
// }

// interface AutoPilotSendResult {
//   sent: number;
//   failed: number;
//   markedOnly: number;
//   total: number;
// }

// interface Prospect {
//   id: string;
//   firstName: string;
//   lastName: string;
//   company: string | null;
// }

// // ─── Constants ────────────────────────────────────────────────────────────────

// const CATEGORY_COLORS: Record<string, string> = {
//   interested:      'bg-emerald-100 text-emerald-700',
//   positive_signal: 'bg-green-100 text-green-700',
//   meeting_request: 'bg-blue-100 text-blue-700',
//   needs_info:      'bg-amber-100 text-amber-700',
//   counter_proposal:'bg-purple-100 text-purple-700',
//   neutral:         'bg-gray-100 text-gray-700',
//   out_of_office:   'bg-sky-100 text-sky-700',
//   not_interested:  'bg-red-100 text-red-700',
//   positive:        'bg-emerald-100 text-emerald-700',
//   objection:       'bg-amber-100 text-amber-700',
//   unsubscribe:     'bg-rose-100 text-rose-700',
//   oof:             'bg-sky-100 text-sky-700',
//   other:           'bg-gray-100 text-gray-700',
// };

// const STATUS_COLORS: Record<string, string> = {
//   pending:   'bg-amber-100 text-amber-700',
//   approved:  'bg-blue-100 text-blue-700',
//   sent:      'bg-emerald-100 text-emerald-700',
//   dismissed: 'bg-gray-100 text-gray-600',
//   auto_sent: 'bg-violet-100 text-violet-700',
// };

// const POSITIVE_CATEGORIES = ['interested', 'meeting_request', 'positive_signal', 'positive'];

// function normalise<T>(data: unknown): T[] {
//   if (!data) return [];
//   if (Array.isArray(data)) return data as T[];
//   return ((data as { items?: T[] }).items) ?? [];
// }

// // ─── Component ────────────────────────────────────────────────────────────────

// export function ReplyInboxPage() {
//   const qc = useQueryClient();

//   const { data: rawReplies, isLoading } = useQuery({
//     queryKey: ['reply-drafts'],
//     queryFn: () => http.get<unknown>('/api/v1/reply-drafts'),
//     refetchInterval: 30_000,
//     retry: false,
//   });
//   const replies = normalise<ReplyDraft>(rawReplies);

//   const { data: autoPilotData } = useQuery({
//     queryKey: ['reply-drafts-autopilot'],
//     queryFn: () => http.get<AutoPilotPreview>('/api/v1/reply-drafts/auto-pilot'),
//     retry: false,
//   });

//   const { data: rawProspects } = useQuery({
//     queryKey: ['prospects-mini'],
//     queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
//     staleTime: 60_000,
//   });
//   const prospects = normalise<Prospect>(rawProspects);

//   const [selectedDraft, setSelectedDraft]         = useState<ReplyDraft | null>(null);
//   const [showAutoPilotOnly, setShowAutoPilotOnly] = useState(false);
//   const [createDealOpen, setCreateDealOpen]       = useState(false);
//   const [dealTitle, setDealTitle]                 = useState('');
//   const [dealValue, setDealValue]                 = useState('');
//   const [dealNotes, setDealNotes]                 = useState('');
//   const [dealNextAction, setDealNextAction]       = useState('');
//   const [dealSuggesting, setDealSuggesting]       = useState(false);

//   const [logOpen, setLogOpen]             = useState(false);
//   const [logProspectId, setLogProspectId] = useState('');
//   const [logSequenceId, setLogSequenceId] = useState('');
//   const [logReplyText, setLogReplyText]   = useState('');
//   const [logSubmitting, setLogSubmitting] = useState(false);

//   // Sequences for the selected prospect (for Log Reply sequenceId)
//   const { data: logSequencesRaw } = useQuery({
//     queryKey: ['sequences-for-log', logProspectId],
//     queryFn: () => http.get<unknown>('/api/v1/sequences', { prospect_id: logProspectId, limit: 50 }),
//     enabled: !!logProspectId,
//     staleTime: 30_000,
//   });
//   const logSequences = normalise<{ id: string; touchNumber: number; angle: string }>(logSequencesRaw);

//   const [apPreviewOpen, setApPreviewOpen]     = useState(false);
//   const [apPreviewLoading, setApPreviewLoading] = useState(false);
//   const [apPreview, setApPreview]             = useState<AutoPilotPreview | null>(null);
//   const [apConfirmOpen, setApConfirmOpen]     = useState(false);
//   const [apSending, setApSending]             = useState(false);
//   const [apResult, setApResult]               = useState<AutoPilotSendResult | null>(null);
//   const [apResultOpen, setApResultOpen]       = useState(false);

//   const filteredDrafts = useMemo(() =>
//     showAutoPilotOnly ? replies.filter((r) => r.autoPilotEligible) : replies,
//     [replies, showAutoPilotOnly]
//   );

//   const autoPilotStats = useMemo(() => ({
//     eligible:      replies.filter((r) => r.autoPilotEligible && r.status === 'pending').length,
//     autoSent:      replies.filter((r) => r.status === 'auto_sent').length,
//     pendingReview: replies.filter((r) => r.status === 'pending').length,
//     total:         replies.length,
//   }), [replies]);

//   const pendingCount = replies.filter((r) => r.status === 'pending').length;

//   useEffect(() => {
//     if (!selectedDraft && filteredDrafts.length > 0) {
//       setSelectedDraft(filteredDrafts[0]);
//     }
//   }, [filteredDrafts, selectedDraft]);

//   const approveMut = useMutation({
//     mutationFn: (id: string) => http.put(`/api/v1/reply-drafts/${id}`, { status: 'approved' }),
//     onSuccess: () => { toast.success('Approved'); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
//     onError: () => toast.error('Approve failed'),
//   });

//   const sendMut = useMutation({
//     mutationFn: (id: string) => http.post(`/api/v1/reply-drafts/${id}/auto-reply`, { dryRun: false }),
//     onSuccess: () => { toast.success('Reply sent!'); setSelectedDraft(null); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
//     onError: () => toast.error('Send failed'),
//   });

//   const dismissMut = useMutation({
//     mutationFn: (id: string) => http.put(`/api/v1/reply-drafts/${id}`, { status: 'dismissed' }),
//     onSuccess: () => { toast.success('Dismissed'); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
//     onError: () => toast.error('Dismiss failed'),
//   });

//   const createDealMut = useMutation({
//     mutationFn: (payload: { title: string; value: number; stage: string; notes?: string; prospectId?: string; source: string }) =>
//       http.post('/api/v1/deals', payload),
//     onSuccess: () => { toast.success('Deal created'); setCreateDealOpen(false); },
//     onError: () => toast.error('Failed to create deal'),
//   });

//   const handleExportCsv = () => {
//     const headers = ['id', 'category', 'status', 'confidence', 'autoPilotEligible', 'originalReply', 'draftBody', 'createdAt'];
//     const csv = [
//       headers.join(','),
//       ...replies.map((r) =>
//         headers.map((h) => {
//           const val = String((r as unknown as Record<string, unknown>)[h] ?? '');
//           return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
//         }).join(',')
//       ),
//     ].join('\n');
//     const blob = new Blob([csv], { type: 'text/csv' });
//     const url = URL.createObjectURL(blob);
//     const a = document.createElement('a');
//     a.href = url; a.download = `reply-drafts-${new Date().toISOString().split('T')[0]}.csv`; a.click();
//     URL.revokeObjectURL(url);
//     toast.success('CSV exported');
//   };

//   const handleLogReply = async () => {
//     if (!logReplyText.trim() || !logProspectId || !logSequenceId) { toast.error('Select a prospect, sequence, and enter reply text'); return; }
//     setLogSubmitting(true);
//     try {
//       await http.post('/api/v1/reply-drafts', { prospectId: logProspectId, sequenceId: logSequenceId, originalReply: logReplyText, category: 'other' });
//       toast.success('Reply logged');
//       setLogOpen(false); setLogProspectId(''); setLogSequenceId(''); setLogReplyText('');
//       qc.invalidateQueries({ queryKey: ['reply-drafts'] });
//     } catch { toast.error('Failed to log reply'); }
//     finally { setLogSubmitting(false); }
//   };

//   const handlePreviewAutoPilot = async () => {
//     setApPreviewLoading(true); setApPreviewOpen(true);
//     try {
//       const result = await http.get<AutoPilotPreview>('/api/v1/reply-drafts/auto-pilot');
//       setApPreview(result);
//     } catch { toast.error('Failed to load preview'); setApPreview({ eligible: [], count: 0 }); }
//     finally { setApPreviewLoading(false); }
//   };

//   const handleRunAutoPilot = async () => {
//     setApConfirmOpen(false); setApSending(true);
//     try {
//       const eligible = apPreview?.eligible ?? autoPilotData?.eligible ?? [];
//       const results = await Promise.allSettled(
//         eligible.map((d) => http.post(`/api/v1/reply-drafts/${d.id}/auto-reply`, { dryRun: false }))
//       );
//       const sent = results.filter((r) => r.status === 'fulfilled').length;
//       const failed = results.filter((r) => r.status === 'rejected').length;
//       setApResult({ sent, failed, markedOnly: 0, total: results.length });
//       setApResultOpen(true);
//       qc.invalidateQueries({ queryKey: ['reply-drafts'] });
//       qc.invalidateQueries({ queryKey: ['reply-drafts-autopilot'] });
//       if (sent > 0) toast.success(`Auto-Pilot sent ${sent} draft${sent === 1 ? '' : 's'}`);
//       if (failed > 0) toast.error(`${failed} draft${failed === 1 ? '' : 's'} failed`);
//     } catch { toast.error('Auto-Pilot run failed'); }
//     finally { setApSending(false); }
//   };

//   const openCreateDeal = async (draft: ReplyDraft) => {
//     setDealTitle(''); setDealValue(''); setDealNotes(''); setDealNextAction('');
//     setCreateDealOpen(true);
//     setDealSuggesting(true);
//     try {
//       const result = await http.post<{ suggestion?: string; nextAction?: string; dealTitle?: string; dealValue?: number; dealNotes?: string }>(
//         `/api/v1/deals/temp/deal-suggest`, { replyDraftId: draft.id }
//       );
//       setDealTitle(result.dealTitle ?? `${draft.category.replace(/_/g, ' ')} — Deal`);
//       setDealValue(String(result.dealValue ?? ''));
//       setDealNotes(result.dealNotes ?? result.suggestion ?? '');
//       setDealNextAction(result.nextAction ?? '');
//     } catch { /* suggestion failed silently */ }
//     finally { setDealSuggesting(false); }
//   };

//   return (
//     <div className="space-y-4">
//       <Tabs defaultValue="manual" className="w-full">
//         <TabsList className="grid w-full max-w-md grid-cols-2">
//           <TabsTrigger value="manual">
//             <MessageCircleReply className="h-3.5 w-3.5 mr-1.5" /> Manual Review
//           </TabsTrigger>
//           <TabsTrigger value="autopilot">
//             <Bot className="h-3.5 w-3.5 mr-1.5" /> Auto-Pilot
//             {autoPilotStats.eligible > 0 && (
//               <Badge className="ml-1.5 bg-violet-100 text-violet-700 border-violet-200 text-[10px] px-1 py-0 border">
//                 {autoPilotStats.eligible}
//               </Badge>
//             )}
//           </TabsTrigger>
//         </TabsList>

//         {/* ── Manual Review Tab ─────────────────────────────────────────── */}
//         <TabsContent value="manual" className="space-y-4 mt-4">
//           <div className="flex items-center gap-3 flex-wrap">
//             {pendingCount > 0 && <Badge variant="default" className="text-xs">{pendingCount} pending</Badge>}
//             <span className="text-xs text-muted-foreground">Auto-refreshes every 30s</span>
//             <Button variant="outline" size="sm" onClick={() => toast.info('Go to Campaigns → Sequences and use the categorize button on a replied sequence')}>
//               <MessageCircleReply className="h-4 w-4 mr-1" /> Categorize Reply
//             </Button>
//             <Button variant="outline" size="sm" onClick={() => setLogOpen(true)}>
//               <MessageCircleReply className="h-4 w-4 mr-1" /> Log a reply
//             </Button>
//             <Button variant="outline" size="sm" onClick={handleExportCsv} disabled={replies.length === 0}>
//               <FileDown className="h-4 w-4 mr-1" /> Export CSV
//             </Button>
//             <div className="ml-auto flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
//               <Switch id="filter-ap" checked={showAutoPilotOnly} onCheckedChange={setShowAutoPilotOnly} />
//               <Label htmlFor="filter-ap" className="text-xs font-medium cursor-pointer flex items-center gap-1">
//                 <Zap className="h-3 w-3 text-violet-600" /> Show only auto-pilot eligible drafts
//               </Label>
//             </div>
//           </div>

//           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
//             {/* Draft list */}
//             <Card>
//               <CardHeader className="pb-2">
//                 <CardTitle className="text-sm flex items-center justify-between">
//                   <span>Reply Drafts {showAutoPilotOnly && <Badge variant="outline" className="ml-2 text-[10px]">filter: auto-pilot eligible</Badge>}</span>
//                   <span className="text-xs text-muted-foreground font-normal">{filteredDrafts.length} shown</span>
//                 </CardTitle>
//               </CardHeader>
//               <CardContent className="p-0">
//                 <div className="max-h-[600px] overflow-y-auto">
//                   {isLoading ? (
//                     <div className="p-6 text-center"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
//                   ) : filteredDrafts.length === 0 ? (
//                     <div className="p-6 text-center text-sm text-muted-foreground">
//                       {showAutoPilotOnly
//                         ? 'No auto-pilot eligible drafts. Eligible drafts are high-confidence positive replies.'
//                         : 'No reply drafts yet. When prospects reply, categorize them from the Sequences page to auto-generate draft responses.'
//                       }
//                     </div>
//                   ) : filteredDrafts.map((d) => (
//                     <button
//                       key={d.id}
//                       onClick={() => setSelectedDraft(d)}
//                       className={cn('w-full text-left p-3 border-b last:border-0 hover:bg-muted/30 transition-colors', selectedDraft?.id === d.id && 'bg-muted/50')}
//                     >
//                       <div className="flex items-center justify-between gap-2">
//                         <div className="flex items-center gap-1.5 flex-wrap">
//                           <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', CATEGORY_COLORS[d.category] ?? 'bg-gray-100')}>
//                             {d.category.replace(/_/g, ' ')}
//                           </span>
//                           {d.autoPilotEligible && (
//                             <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-100 text-violet-700 flex items-center gap-0.5">
//                               <Zap className="h-2.5 w-2.5" /> auto-pilot
//                             </span>
//                           )}
//                         </div>
//                         <span className={cn('px-1.5 py-0.5 rounded text-[10px] shrink-0', STATUS_COLORS[d.status] ?? 'bg-gray-100')}>
//                           {d.status.replace('_', ' ')}
//                         </span>
//                       </div>
//                       <p className="text-xs font-medium mt-1.5 line-clamp-1">{d.originalReply}</p>
//                       {d.draftBody && <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{d.draftBody}</p>}
//                       <p className="text-[10px] text-muted-foreground mt-1">{new Date(d.createdAt).toLocaleString()}</p>
//                     </button>
//                   ))}
//                 </div>
//               </CardContent>
//             </Card>

//             {/* Detail panel */}
//             <Card>
//               <CardHeader className="pb-2"><CardTitle className="text-sm">Draft Detail</CardTitle></CardHeader>
//               <CardContent>
//                 {!selectedDraft ? (
//                   <p className="text-sm text-muted-foreground">Select a draft to view details and take action.</p>
//                 ) : (
//                   <div className="space-y-4">
//                     <div className="flex items-center gap-2 flex-wrap">
//                       <span className={cn('px-2 py-0.5 rounded text-xs font-medium', CATEGORY_COLORS[selectedDraft.category] ?? 'bg-gray-100')}>
//                         {selectedDraft.category.replace(/_/g, ' ')}
//                       </span>
//                       <span className={cn('px-2 py-0.5 rounded text-xs', STATUS_COLORS[selectedDraft.status] ?? 'bg-gray-100')}>
//                         {selectedDraft.status.replace('_', ' ')}
//                       </span>
//                       {selectedDraft.autoPilotEligible && (
//                         <span className="px-2 py-0.5 rounded text-xs font-medium bg-violet-100 text-violet-700 flex items-center gap-1">
//                           <Zap className="h-3 w-3" /> auto-pilot eligible
//                         </span>
//                       )}
//                       {selectedDraft.summary && <span className="text-xs text-muted-foreground">{selectedDraft.summary}</span>}
//                       {selectedDraft.confidence != null && (
//                         <span className="text-xs text-muted-foreground">confidence: {Math.round(selectedDraft.confidence * 100)}%</span>
//                       )}
//                     </div>

//                     <div>
//                       <p className="text-xs font-medium mb-1">Original Reply</p>
//                       <div className="bg-muted/50 rounded-lg p-3 text-sm border">{selectedDraft.originalReply}</div>
//                     </div>

//                     {selectedDraft.suggestedAction && (
//                       <div>
//                         <p className="text-xs font-medium mb-1">Suggested Action</p>
//                         <p className="text-sm text-muted-foreground">{selectedDraft.suggestedAction}</p>
//                       </div>
//                     )}

//                     {selectedDraft.draftBody && (
//                       <div>
//                         <p className="text-xs font-medium mb-1">AI-Generated Draft</p>
//                         <div className="bg-emerald-50/50 border border-emerald-200 rounded-lg p-3 text-sm whitespace-pre-wrap">{selectedDraft.draftBody}</div>
//                       </div>
//                     )}

//                     <div className="flex gap-2 flex-wrap">
//                       {selectedDraft.status === 'pending' && (
//                         <>
//                           <Button size="sm" onClick={() => approveMut.mutate(selectedDraft.id)} disabled={approveMut.isPending}>
//                             <CheckCircle2 className="h-4 w-4 mr-1" /> Approve
//                           </Button>
//                           <Button size="sm" variant="outline" onClick={() => sendMut.mutate(selectedDraft.id)} disabled={sendMut.isPending}>
//                             <Send className="h-4 w-4 mr-1" />{sendMut.isPending ? 'Sending…' : 'Send Now'}
//                           </Button>
//                           <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
//                             onClick={() => dismissMut.mutate(selectedDraft.id)} disabled={dismissMut.isPending}>
//                             <Ban className="h-4 w-4 mr-1" /> Dismiss
//                           </Button>
//                         </>
//                       )}
//                       {selectedDraft.status === 'approved' && (
//                         <Button size="sm" onClick={() => sendMut.mutate(selectedDraft.id)} disabled={sendMut.isPending}>
//                           <Send className="h-4 w-4 mr-1" />{sendMut.isPending ? 'Sending…' : 'Send Now'}
//                         </Button>
//                       )}
//                       {(selectedDraft.status === 'sent' || selectedDraft.status === 'auto_sent') && (
//                         <Badge className="bg-emerald-100 text-emerald-700">
//                           <CheckCircle2 className="h-3 w-3 mr-1" />
//                           {selectedDraft.status === 'auto_sent' ? 'Auto-Sent' : 'Sent'}
//                         </Badge>
//                       )}
//                       {POSITIVE_CATEGORIES.includes(selectedDraft.category) && (
//                         <Button size="sm" variant="outline" className="text-emerald-700 border-emerald-300 hover:bg-emerald-50"
//                           onClick={() => openCreateDeal(selectedDraft)}>
//                           <DollarSign className="h-4 w-4 mr-1" />
//                           {dealSuggesting && createDealOpen ? 'Analyzing…' : 'Create Deal'}
//                         </Button>
//                       )}
//                     </div>

//                     {/* Inline deal form */}
//                     {createDealOpen && (
//                       <Card className="border-emerald-200 bg-emerald-50/50">
//                         <CardContent className="p-3 space-y-2">
//                           <p className="text-xs font-medium flex items-center gap-1">
//                             <Sparkles className="h-3 w-3" /> AI-Suggested Deal
//                           </p>
//                           <div className="grid grid-cols-2 gap-2">
//                             <div>
//                               <Label className="text-xs">Deal Title</Label>
//                               <Input className="h-8 text-sm mt-1" value={dealTitle} onChange={(e) => setDealTitle(e.target.value)} />
//                             </div>
//                             <div>
//                               <Label className="text-xs">Value ($)</Label>
//                               <Input className="h-8 text-sm mt-1" type="number" placeholder="0" value={dealValue} onChange={(e) => setDealValue(e.target.value)} />
//                             </div>
//                           </div>
//                           {dealNotes && (
//                             <div>
//                               <Label className="text-xs">AI Notes</Label>
//                               <p className="text-xs text-muted-foreground mt-1 bg-white rounded p-2 border">{dealNotes}</p>
//                             </div>
//                           )}
//                           {dealNextAction && (
//                             <div>
//                               <Label className="text-xs">Suggested Next Action</Label>
//                               <p className="text-xs text-emerald-800 mt-1 bg-white rounded p-2 border border-emerald-200">{dealNextAction}</p>
//                             </div>
//                           )}
//                           <div className="flex gap-2">
//                             <Button size="sm" disabled={!dealTitle || createDealMut.isPending}
//                               onClick={() => createDealMut.mutate({ title: dealTitle, value: parseFloat(dealValue) || 0, stage: 'qualified', notes: dealNotes || undefined, prospectId: selectedDraft?.prospectId, source: 'cold_email' })}>
//                               {createDealMut.isPending ? 'Creating…' : 'Create Deal'}
//                             </Button>
//                             <Button size="sm" variant="ghost" onClick={() => setCreateDealOpen(false)}>Cancel</Button>
//                           </div>
//                         </CardContent>
//                       </Card>
//                     )}
//                   </div>
//                 )}
//               </CardContent>
//             </Card>
//           </div>

//           {/* Workflow info card */}
//           <Card className="border-blue-100 bg-blue-50/50">
//             <CardContent className="p-4">
//               <div className="flex items-start gap-3">
//                 <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
//                 <div className="text-xs text-blue-800 space-y-1">
//                   <p className="font-medium">Auto-Draft Reply Workflow</p>
//                   <p>When a prospect replies to your email: 1) Go to <b>Campaigns &gt; Sequences</b> and click the reply categorize button on a replied sequence. 2) AI categorizes the intent and generates a draft response. 3) Review, approve, and send — nothing goes out without your approval.</p>
//                 </div>
//               </div>
//             </CardContent>
//           </Card>
//         </TabsContent>

//         {/* ── Auto-Pilot Tab ─────────────────────────────────────────────── */}
//         <TabsContent value="autopilot" className="space-y-4 mt-4">
//           <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
//             <Card className="border-violet-200 bg-violet-50/30">
//               <CardContent className="p-4">
//                 <div className="flex items-center gap-2 text-violet-700"><Zap className="h-4 w-4" /><span className="text-xs font-medium">Eligible</span></div>
//                 <p className="text-2xl font-bold mt-1">{autoPilotStats.eligible}</p>
//                 <p className="text-[11px] text-muted-foreground">Pending + auto-pilot eligible</p>
//               </CardContent>
//             </Card>
//             <Card className="border-emerald-200 bg-emerald-50/30">
//               <CardContent className="p-4">
//                 <div className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="h-4 w-4" /><span className="text-xs font-medium">Auto-Sent</span></div>
//                 <p className="text-2xl font-bold mt-1">{autoPilotStats.autoSent}</p>
//                 <p className="text-[11px] text-muted-foreground">Already sent via Auto-Pilot</p>
//               </CardContent>
//             </Card>
//             <Card className="border-amber-200 bg-amber-50/30">
//               <CardContent className="p-4">
//                 <div className="flex items-center gap-2 text-amber-700"><Clock className="h-4 w-4" /><span className="text-xs font-medium">Pending Review</span></div>
//                 <p className="text-2xl font-bold mt-1">{autoPilotStats.pendingReview}</p>
//                 <p className="text-[11px] text-muted-foreground">All drafts awaiting your action</p>
//               </CardContent>
//             </Card>
//             <Card>
//               <CardContent className="p-4">
//                 <div className="flex items-center gap-2 text-muted-foreground"><MessageCircleReply className="h-4 w-4" /><span className="text-xs font-medium">Total Drafts</span></div>
//                 <p className="text-2xl font-bold mt-1">{autoPilotStats.total}</p>
//                 <p className="text-[11px] text-muted-foreground">All reply drafts</p>
//               </CardContent>
//             </Card>
//           </div>

//           <Card className="border-violet-200 bg-gradient-to-br from-violet-50/60 to-white">
//             <CardHeader>
//               <CardTitle className="text-base flex items-center gap-2"><Bot className="h-4 w-4 text-violet-600" /> Auto-Pilot Reply Sender</CardTitle>
//               <CardDescription>
//                 Auto-send high-confidence positive replies. Drafts with category <code className="text-[10px] bg-muted px-1 py-0.5 rounded">interested</code>, <code className="text-[10px] bg-muted px-1 py-0.5 rounded">meeting_request</code>, <code className="text-[10px] bg-muted px-1 py-0.5 rounded">positive</code> with confidence ≥ 80% are eligible.
//               </CardDescription>
//             </CardHeader>
//             <CardContent className="space-y-4">
//               <div className="flex flex-wrap gap-2">
//                 <Button variant="outline" onClick={handlePreviewAutoPilot} disabled={apPreviewLoading}>
//                   {apPreviewLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Eye className="h-4 w-4 mr-1.5" />}
//                   Preview Auto-Pilot
//                 </Button>
//                 <Button className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white"
//                   onClick={() => { if (autoPilotStats.eligible === 0) { toast.info('No eligible drafts to auto-send.'); return; } setApConfirmOpen(true); }}
//                   disabled={apSending}>
//                   {apSending ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Send className="h-4 w-4 mr-1.5" />}
//                   Run Auto-Pilot ({autoPilotStats.eligible} draft{autoPilotStats.eligible === 1 ? '' : 's'})
//                 </Button>
//               </div>
//               {apSending && (
//                 <div className="rounded-md bg-violet-50 border border-violet-200 p-3 text-xs text-violet-800 flex items-center gap-2">
//                   <Loader2 className="h-3.5 w-3.5 animate-spin" /> Auto-Pilot is sending eligible drafts via MailBridge…
//                 </div>
//               )}
//               <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-xs text-blue-800 space-y-1">
//                 <p className="font-medium flex items-center gap-1.5"><Info className="h-3.5 w-3.5" /> How Auto-Pilot works</p>
//                 <ol className="list-decimal list-inside space-y-0.5 ml-1">
//                   <li>Click <b>Preview Auto-Pilot</b> to dry-run — see exactly which drafts would be sent.</li>
//                   <li>Click <b>Run Auto-Pilot</b> to actually send. You'll get a confirmation dialog first.</li>
//                   <li>If MailBridge is connected, drafts are sent via your sending domain. Otherwise, drafts are marked <code className="text-[10px] bg-white px-1 py-0.5 rounded">auto_sent</code> but not delivered.</li>
//                   <li>Failed sends stay in <code className="text-[10px] bg-white px-1 py-0.5 rounded">pending</code> so you can retry manually.</li>
//                 </ol>
//               </div>
//             </CardContent>
//           </Card>
//         </TabsContent>
//       </Tabs>

//       {/* Log a Reply Dialog — with prospect selector */}
//       <Dialog open={logOpen} onOpenChange={setLogOpen}>
//         <DialogContent>
//           <DialogHeader>
//             <DialogTitle>Log a Reply</DialogTitle>
//             <DialogDescription>Paste an external reply that wasn't captured by MailBridge.</DialogDescription>
//           </DialogHeader>
//           <div className="space-y-3">
//             <div className="space-y-1">
//               <Label>Prospect <span className="text-destructive">*</span></Label>
//               <Select value={logProspectId} onValueChange={(v) => { setLogProspectId(v); setLogSequenceId(''); }}>
//                 <SelectTrigger><SelectValue placeholder="Select prospect…" /></SelectTrigger>
//                 <SelectContent className="max-h-64">
//                   {prospects.map((p) => (
//                     <SelectItem key={p.id} value={p.id}>
//                       {p.firstName} {p.lastName}{p.company ? ` — ${p.company}` : ''}
//                     </SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>
//             <div className="space-y-1">
//               <Label>Sequence (Touch) <span className="text-destructive">*</span></Label>
//               <Select value={logSequenceId} onValueChange={setLogSequenceId} disabled={!logProspectId}>
//                 <SelectTrigger><SelectValue placeholder={logProspectId ? 'Select sequence…' : 'Select a prospect first'} /></SelectTrigger>
//                 <SelectContent className="max-h-64">
//                   {logSequences.map((s) => (
//                     <SelectItem key={s.id} value={s.id}>
//                       Touch {s.touchNumber} — {s.angle.replace(/_/g, ' ')}
//                     </SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>
//             <div className="space-y-1">
//               <Label>Reply Text <span className="text-destructive">*</span></Label>
//               <Textarea rows={5} value={logReplyText} onChange={(e) => setLogReplyText(e.target.value)} placeholder="Paste the prospect's reply here…" />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setLogOpen(false)}>Cancel</Button>
//             <Button disabled={!logReplyText.trim() || !logProspectId || !logSequenceId || logSubmitting} onClick={handleLogReply}>
//               {logSubmitting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} Log Reply
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>

//       {/* Auto-Pilot Preview Dialog */}
//       <Dialog open={apPreviewOpen} onOpenChange={setApPreviewOpen}>
//         <DialogContent className="sm:max-w-2xl">
//           <DialogHeader>
//             <DialogTitle className="flex items-center gap-2"><Eye className="h-4 w-4 text-violet-600" /> Auto-Pilot Preview (Dry-Run)</DialogTitle>
//             <DialogDescription>
//               {apPreviewLoading ? 'Loading…' : `${apPreview?.count ?? 0} draft${(apPreview?.count ?? 0) === 1 ? '' : 's'} would be sent.`}
//             </DialogDescription>
//           </DialogHeader>
//           {apPreviewLoading ? (
//             <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
//           ) : (
//             <div className="max-h-72 overflow-y-auto space-y-2">
//               {(apPreview?.eligible ?? []).length === 0
//                 ? <p className="text-sm text-muted-foreground text-center py-4">No eligible drafts.</p>
//                 : (apPreview?.eligible ?? []).map((d) => (
//                   <div key={d.id} className="p-3 rounded-lg border text-sm space-y-1">
//                     <div className="flex items-center justify-between">
//                       <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', CATEGORY_COLORS[d.category] ?? 'bg-gray-100')}>
//                         {d.category.replace(/_/g, ' ')}
//                       </span>
//                       <span className="text-xs text-muted-foreground">{d.confidence != null ? `${Math.round(d.confidence * 100)}% confidence` : ''}</span>
//                     </div>
//                     <p className="text-xs text-muted-foreground line-clamp-2">{d.draftBody ?? d.originalReply}</p>
//                   </div>
//                 ))
//               }
//             </div>
//           )}
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setApPreviewOpen(false)}>Close</Button>
//             <Button onClick={() => { setApPreviewOpen(false); setApConfirmOpen(true); }} disabled={(apPreview?.count ?? 0) === 0}>
//               Proceed to Send All
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>

//       {/* Auto-Pilot Confirm Dialog */}
//       <Dialog open={apConfirmOpen} onOpenChange={setApConfirmOpen}>
//         <DialogContent className="sm:max-w-md">
//           <DialogHeader>
//             <DialogTitle className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-amber-600" /> Confirm Auto-Pilot Send</DialogTitle>
//             <DialogDescription>
//               This will send <strong>{autoPilotStats.eligible}</strong> eligible draft{autoPilotStats.eligible === 1 ? '' : 's'} via MailBridge. Cannot be undone.
//             </DialogDescription>
//           </DialogHeader>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setApConfirmOpen(false)}>Cancel</Button>
//             <Button className="bg-violet-600 hover:bg-violet-700 text-white" onClick={handleRunAutoPilot} disabled={apSending}>
//               {apSending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />} Run Auto-Pilot
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>

//       {/* Auto-Pilot Result Dialog */}
//       <Dialog open={apResultOpen} onOpenChange={setApResultOpen}>
//         <DialogContent className="sm:max-w-md">
//           <DialogHeader>
//             <DialogTitle className="flex items-center gap-2">
//               {(apResult?.failed ?? 0) === 0 ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-red-600" />}
//               Auto-Pilot Results
//             </DialogTitle>
//             <DialogDescription>Send run complete.</DialogDescription>
//           </DialogHeader>
//           {apResult && (
//             <div className="grid grid-cols-3 gap-4 py-2">
//               {[{ label: 'Sent', value: apResult.sent, color: 'text-emerald-600' }, { label: 'Failed', value: apResult.failed, color: 'text-red-600' }, { label: 'Total', value: apResult.total, color: 'text-foreground' }].map((s) => (
//                 <div key={s.label} className="text-center p-3 rounded-lg border">
//                   <p className={cn('text-2xl font-bold', s.color)}>{s.value}</p>
//                   <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
//                 </div>
//               ))}
//             </div>
//           )}
//           <DialogFooter><Button onClick={() => setApResultOpen(false)}>Done</Button></DialogFooter>
//         </DialogContent>
//       </Dialog>
//     </div>
//   );
// }

/**
 * ReplyInboxPage.tsx
 *
 * Shows a conversation-thread view for each reply draft:
 *   1. What Outrena sent (from Sequence.subjectLine + bodyCopy)
 *   2. What the prospect replied (ReplyDraft.originalReply)
 *   3. The AI-generated draft reply (ReplyDraft.draftBody)
 *
 * The left panel is a list of drafts grouped by prospect.
 * The right panel is the conversation thread + action buttons.
 */
import { useMemo, useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bot, CheckCircle2, Send, Sparkles, FileDown, Eye, Info,
  Loader2, MessageCircleReply, Zap, Ban, DollarSign, Clock,
  ShieldAlert, XCircle, Mail, User, ArrowDown,
} from 'lucide-react';
import { toast } from 'sonner';

import { http } from '@/services/apiClient';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ReplyDraft {
  id: string;
  sequenceId: string;
  prospectId: string;
  originalReply: string;
  category: string;
  summary: string | null;
  suggestedAction: string | null;
  draftBody: string | null;
  status: string;
  sentAt: string | null;
  autoPilotEligible: boolean;
  confidence: number | null;
  autoSentAt: string | null;
  createdAt: string;
  updatedAt: string;
  // Enriched fields from backend join
  prospectName: string | null;
  prospectEmail: string | null;
  sentEmailSubject: string | null;
  sentEmailBody: string | null;
}

interface AutoPilotPreview {
  eligible: ReplyDraft[];
  count: number;
}

interface AutoPilotSendResult {
  sent: number;
  failed: number;
  markedOnly: number;
  total: number;
}

interface Prospect {
  id: string;
  firstName: string;
  lastName: string;
  company: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  interested:      'bg-emerald-100 text-emerald-700',
  positive_signal: 'bg-green-100 text-green-700',
  meeting_request: 'bg-blue-100 text-blue-700',
  needs_info:      'bg-amber-100 text-amber-700',
  counter_proposal:'bg-purple-100 text-purple-700',
  neutral:         'bg-gray-100 text-gray-700',
  out_of_office:   'bg-sky-100 text-sky-700',
  not_interested:  'bg-red-100 text-red-700',
  positive:        'bg-emerald-100 text-emerald-700',
  objection:       'bg-amber-100 text-amber-700',
  unsubscribe:     'bg-rose-100 text-rose-700',
  oof:             'bg-sky-100 text-sky-700',
  other:           'bg-gray-100 text-gray-700',
};

const STATUS_COLORS: Record<string, string> = {
  pending:   'bg-amber-100 text-amber-700',
  approved:  'bg-blue-100 text-blue-700',
  sent:      'bg-emerald-100 text-emerald-700',
  dismissed: 'bg-gray-100 text-gray-600',
  auto_sent: 'bg-violet-100 text-violet-700',
};

const POSITIVE_CATEGORIES = ['interested', 'meeting_request', 'positive_signal', 'positive'];

function normalise<T>(data: unknown): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  return ((data as { items?: T[] }).items) ?? [];
}

// ─── Conversation Thread Component ───────────────────────────────────────────

function ConversationThread({ draft }: { draft: ReplyDraft }) {
  const prospectLabel = draft.prospectName ?? draft.prospectEmail ?? 'Prospect';

  return (
    <div className="space-y-3">
      {/* ── Step 1: What Outrena sent ─────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
          <Mail className="h-3 w-3" /> You sent
        </div>
        <div className="rounded-lg border bg-muted/30 p-3 text-sm">
          {draft.sentEmailSubject && (
            <p className="font-medium text-xs text-muted-foreground mb-1.5">
              Subject: {draft.sentEmailSubject}
            </p>
          )}
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {draft.sentEmailBody ?? (
              <span className="italic text-muted-foreground">
                Email body not captured — check Sequence details.
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Arrow connector */}
      <div className="flex items-center justify-center text-muted-foreground/40">
        <ArrowDown className="h-4 w-4" />
      </div>

      {/* ── Step 2: Prospect's reply ───────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
          <User className="h-3 w-3" />
          <span>{prospectLabel} replied</span>
          {draft.prospectEmail && (
            <span className="normal-case font-normal text-muted-foreground/60">
              &lt;{draft.prospectEmail}&gt;
            </span>
          )}
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-3">
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{draft.originalReply}</p>
        </div>
      </div>

      {/* Arrow connector (only show if there's a draft) */}
      {draft.draftBody && (
        <div className="flex items-center justify-center text-muted-foreground/40">
          <ArrowDown className="h-4 w-4" />
        </div>
      )}

      {/* ── Step 3: AI-Generated Draft ────────────────────────────────── */}
      {draft.draftBody && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
            <Sparkles className="h-3 w-3 text-emerald-600" />
            <span className="text-emerald-700">AI-Generated Draft</span>
            {draft.suggestedAction && (
              <span className="normal-case font-normal text-muted-foreground/60 ml-1">
                · {draft.suggestedAction}
              </span>
            )}
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3">
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{draft.draftBody}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ReplyInboxPage() {
  const qc = useQueryClient();

  const { data: rawReplies, isLoading } = useQuery({
    queryKey: ['reply-drafts'],
    queryFn: () => http.get<unknown>('/api/v1/reply-drafts'),
    refetchInterval: 30_000,
    retry: false,
  });
  const replies = normalise<ReplyDraft>(rawReplies);

  const { data: autoPilotData } = useQuery({
    queryKey: ['reply-drafts-autopilot'],
    queryFn: () => http.get<AutoPilotPreview>('/api/v1/reply-drafts/auto-pilot'),
    retry: false,
  });

  const { data: rawProspects } = useQuery({
    queryKey: ['prospects-mini'],
    queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
    staleTime: 60_000,
  });
  const prospects = normalise<Prospect>(rawProspects);

  const [selectedDraft, setSelectedDraft]         = useState<ReplyDraft | null>(null);
  const [showAutoPilotOnly, setShowAutoPilotOnly] = useState(false);
  const [createDealOpen, setCreateDealOpen]       = useState(false);
  const [dealTitle, setDealTitle]                 = useState('');
  const [dealValue, setDealValue]                 = useState('');
  const [dealNotes, setDealNotes]                 = useState('');
  const [dealNextAction, setDealNextAction]       = useState('');
  const [dealSuggesting, setDealSuggesting]       = useState(false);

  const [logOpen, setLogOpen]             = useState(false);
  const [logProspectId, setLogProspectId] = useState('');
  const [logSequenceId, setLogSequenceId] = useState('');
  const [logReplyText, setLogReplyText]   = useState('');
  const [logSubmitting, setLogSubmitting] = useState(false);

  const { data: logSequencesRaw } = useQuery({
    queryKey: ['sequences-for-log', logProspectId],
    queryFn: () => http.get<unknown>('/api/v1/sequences', { prospect_id: logProspectId, limit: 50 }),
    enabled: !!logProspectId,
    staleTime: 30_000,
  });
  const logSequences = normalise<{ id: string; touchNumber: number; angle: string }>(logSequencesRaw);

  const [apPreviewOpen, setApPreviewOpen]       = useState(false);
  const [apPreviewLoading, setApPreviewLoading] = useState(false);
  const [apPreview, setApPreview]               = useState<AutoPilotPreview | null>(null);
  const [apConfirmOpen, setApConfirmOpen]       = useState(false);
  const [apSending, setApSending]               = useState(false);
  const [apResult, setApResult]                 = useState<AutoPilotSendResult | null>(null);
  const [apResultOpen, setApResultOpen]         = useState(false);

  const filteredDrafts = useMemo(() =>
    showAutoPilotOnly ? replies.filter((r) => r.autoPilotEligible) : replies,
    [replies, showAutoPilotOnly]
  );

  const autoPilotStats = useMemo(() => ({
    eligible:      replies.filter((r) => r.autoPilotEligible && r.status === 'pending').length,
    autoSent:      replies.filter((r) => r.status === 'auto_sent').length,
    pendingReview: replies.filter((r) => r.status === 'pending').length,
    total:         replies.length,
  }), [replies]);

  const pendingCount = replies.filter((r) => r.status === 'pending').length;

  useEffect(() => {
    if (!selectedDraft && filteredDrafts.length > 0) {
      setSelectedDraft(filteredDrafts[0]);
    }
  }, [filteredDrafts, selectedDraft]);

  // When the list refreshes, keep selectedDraft in sync so enriched fields update.
  useEffect(() => {
    if (selectedDraft) {
      const fresh = filteredDrafts.find((d) => d.id === selectedDraft.id);
      if (fresh) setSelectedDraft(fresh);
    }
  }, [filteredDrafts]); // eslint-disable-line react-hooks/exhaustive-deps

  const approveMut = useMutation({
    mutationFn: (id: string) => http.put(`/api/v1/reply-drafts/${id}`, { status: 'approved' }),
    onSuccess: () => { toast.success('Approved'); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
    onError: () => toast.error('Approve failed'),
  });

  const sendMut = useMutation({
    mutationFn: (id: string) => http.post(`/api/v1/reply-drafts/${id}/auto-reply`, { dryRun: false }),
    onSuccess: () => { toast.success('Reply sent!'); setSelectedDraft(null); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
    onError: () => toast.error('Send failed'),
  });

  const dismissMut = useMutation({
    mutationFn: (id: string) => http.put(`/api/v1/reply-drafts/${id}`, { status: 'dismissed' }),
    onSuccess: () => { toast.success('Dismissed'); qc.invalidateQueries({ queryKey: ['reply-drafts'] }); },
    onError: () => toast.error('Dismiss failed'),
  });

  const createDealMut = useMutation({
    mutationFn: (payload: { title: string; value: number; stage: string; notes?: string; prospectId?: string; source: string }) =>
      http.post('/api/v1/deals', payload),
    onSuccess: () => { toast.success('Deal created'); setCreateDealOpen(false); },
    onError: () => toast.error('Failed to create deal'),
  });

  const handleExportCsv = () => {
    const headers = ['id', 'category', 'status', 'confidence', 'autoPilotEligible', 'prospectName', 'prospectEmail', 'sentEmailSubject', 'originalReply', 'draftBody', 'createdAt'];
    const csv = [
      headers.join(','),
      ...replies.map((r) =>
        headers.map((h) => {
          const val = String((r as unknown as Record<string, unknown>)[h] ?? '');
          return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
        }).join(',')
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `reply-drafts-${new Date().toISOString().split('T')[0]}.csv`; a.click();
    URL.revokeObjectURL(url);
    toast.success('CSV exported');
  };

  const handleLogReply = async () => {
    if (!logReplyText.trim() || !logProspectId || !logSequenceId) { toast.error('Select a prospect, sequence, and enter reply text'); return; }
    setLogSubmitting(true);
    try {
      await http.post('/api/v1/reply-drafts', { prospectId: logProspectId, sequenceId: logSequenceId, originalReply: logReplyText, category: 'other' });
      toast.success('Reply logged');
      setLogOpen(false); setLogProspectId(''); setLogSequenceId(''); setLogReplyText('');
      qc.invalidateQueries({ queryKey: ['reply-drafts'] });
    } catch { toast.error('Failed to log reply'); }
    finally { setLogSubmitting(false); }
  };

  const handlePreviewAutoPilot = async () => {
    setApPreviewLoading(true); setApPreviewOpen(true);
    try {
      const result = await http.get<AutoPilotPreview>('/api/v1/reply-drafts/auto-pilot');
      setApPreview(result);
    } catch { toast.error('Failed to load preview'); setApPreview({ eligible: [], count: 0 }); }
    finally { setApPreviewLoading(false); }
  };

  const handleRunAutoPilot = async () => {
    setApConfirmOpen(false); setApSending(true);
    try {
      const eligible = apPreview?.eligible ?? autoPilotData?.eligible ?? [];
      const results = await Promise.allSettled(
        eligible.map((d) => http.post(`/api/v1/reply-drafts/${d.id}/auto-reply`, { dryRun: false }))
      );
      const sent = results.filter((r) => r.status === 'fulfilled').length;
      const failed = results.filter((r) => r.status === 'rejected').length;
      setApResult({ sent, failed, markedOnly: 0, total: results.length });
      setApResultOpen(true);
      qc.invalidateQueries({ queryKey: ['reply-drafts'] });
      qc.invalidateQueries({ queryKey: ['reply-drafts-autopilot'] });
      if (sent > 0) toast.success(`Auto-Pilot sent ${sent} draft${sent === 1 ? '' : 's'}`);
      if (failed > 0) toast.error(`${failed} draft${failed === 1 ? '' : 's'} failed`);
    } catch { toast.error('Auto-Pilot run failed'); }
    finally { setApSending(false); }
  };

  const openCreateDeal = async (draft: ReplyDraft) => {
    setDealTitle(''); setDealValue(''); setDealNotes(''); setDealNextAction('');
    setCreateDealOpen(true);
    setDealSuggesting(true);
    try {
      const result = await http.post<{ suggestion?: string; nextAction?: string; dealTitle?: string; dealValue?: number; dealNotes?: string }>(
        `/api/v1/deals/temp/deal-suggest`, { replyDraftId: draft.id }
      );
      setDealTitle(result.dealTitle ?? `${draft.category.replace(/_/g, ' ')} — Deal`);
      setDealValue(String(result.dealValue ?? ''));
      setDealNotes(result.dealNotes ?? result.suggestion ?? '');
      setDealNextAction(result.nextAction ?? '');
    } catch { /* suggestion failed silently */ }
    finally { setDealSuggesting(false); }
  };

  return (
    <div className="space-y-4">
      <Tabs defaultValue="manual" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="manual">
            <MessageCircleReply className="h-3.5 w-3.5 mr-1.5" /> Manual Review
          </TabsTrigger>
          <TabsTrigger value="autopilot">
            <Bot className="h-3.5 w-3.5 mr-1.5" /> Auto-Pilot
            {autoPilotStats.eligible > 0 && (
              <Badge className="ml-1.5 bg-violet-100 text-violet-700 border-violet-200 text-[10px] px-1 py-0 border">
                {autoPilotStats.eligible}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ── Manual Review Tab ─────────────────────────────────────────── */}
        <TabsContent value="manual" className="space-y-4 mt-4">
          <div className="flex items-center gap-3 flex-wrap">
            {pendingCount > 0 && <Badge variant="default" className="text-xs">{pendingCount} pending</Badge>}
            <span className="text-xs text-muted-foreground">Auto-refreshes every 30s</span>
            <Button variant="outline" size="sm" onClick={() => toast.info('Go to Campaigns → Sequences and use the categorize button on a replied sequence')}>
              <MessageCircleReply className="h-4 w-4 mr-1" /> Categorize Reply
            </Button>
            <Button variant="outline" size="sm" onClick={() => setLogOpen(true)}>
              <MessageCircleReply className="h-4 w-4 mr-1" /> Log a reply
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportCsv} disabled={replies.length === 0}>
              <FileDown className="h-4 w-4 mr-1" /> Export CSV
            </Button>
            <div className="ml-auto flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5">
              <Switch id="filter-ap" checked={showAutoPilotOnly} onCheckedChange={setShowAutoPilotOnly} />
              <Label htmlFor="filter-ap" className="text-xs font-medium cursor-pointer flex items-center gap-1">
                <Zap className="h-3 w-3 text-violet-600" /> Show only auto-pilot eligible drafts
              </Label>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* ── Left: Draft List ─────────────────────────────────────── */}
            <Card className="lg:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>
                    Reply Drafts
                    {showAutoPilotOnly && (
                      <Badge variant="outline" className="ml-2 text-[10px]">filter: auto-pilot eligible</Badge>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground font-normal">{filteredDrafts.length} shown</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-[640px] overflow-y-auto">
                  {isLoading ? (
                    <div className="p-6 text-center"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
                  ) : filteredDrafts.length === 0 ? (
                    <div className="p-6 text-center text-sm text-muted-foreground">
                      {showAutoPilotOnly
                        ? 'No auto-pilot eligible drafts. Eligible drafts are high-confidence positive replies.'
                        : 'No reply drafts yet. When prospects reply, categorize them from the Sequences page to auto-generate draft responses.'
                      }
                    </div>
                  ) : filteredDrafts.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => setSelectedDraft(d)}
                      className={cn(
                        'w-full text-left p-3 border-b last:border-0 hover:bg-muted/30 transition-colors',
                        selectedDraft?.id === d.id && 'bg-muted/50 border-l-2 border-l-primary'
                      )}
                    >
                      {/* Prospect name + status badge */}
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-xs font-semibold truncate">
                          {d.prospectName ?? d.prospectEmail ?? 'Unknown Prospect'}
                        </span>
                        <span className={cn('px-1.5 py-0.5 rounded text-[10px] shrink-0', STATUS_COLORS[d.status] ?? 'bg-gray-100')}>
                          {d.status.replace('_', ' ')}
                        </span>
                      </div>

                      {/* Category + auto-pilot badge */}
                      <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                        <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', CATEGORY_COLORS[d.category] ?? 'bg-gray-100')}>
                          {d.category.replace(/_/g, ' ')}
                        </span>
                        {d.autoPilotEligible && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-100 text-violet-700 flex items-center gap-0.5">
                            <Zap className="h-2.5 w-2.5" /> auto-pilot
                          </span>
                        )}
                      </div>

                      {/* Subject line of sent email */}
                      {d.sentEmailSubject && (
                        <p className="text-[10px] text-muted-foreground mb-0.5 truncate">
                          📧 {d.sentEmailSubject}
                        </p>
                      )}

                      {/* Prospect reply snippet */}
                      <p className="text-xs text-foreground/80 line-clamp-2 leading-snug">{d.originalReply}</p>

                      <p className="text-[10px] text-muted-foreground mt-1">{new Date(d.createdAt).toLocaleString()}</p>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* ── Right: Conversation Thread + Actions ─────────────────── */}
            <Card className="lg:col-span-3">
              {!selectedDraft ? (
                <CardContent className="flex items-center justify-center h-full min-h-[200px]">
                  <p className="text-sm text-muted-foreground">Select a reply to view the conversation thread.</p>
                </CardContent>
              ) : (
                <>
                  <CardHeader className="pb-3 border-b">
                    {/* Header: prospect name + meta */}
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div>
                        <CardTitle className="text-base">
                          {selectedDraft.prospectName ?? selectedDraft.prospectEmail ?? 'Unknown Prospect'}
                        </CardTitle>
                        {selectedDraft.prospectEmail && (
                          <p className="text-xs text-muted-foreground mt-0.5">{selectedDraft.prospectEmail}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', CATEGORY_COLORS[selectedDraft.category] ?? 'bg-gray-100')}>
                          {selectedDraft.category.replace(/_/g, ' ')}
                        </span>
                        <span className={cn('px-2 py-0.5 rounded text-xs', STATUS_COLORS[selectedDraft.status] ?? 'bg-gray-100')}>
                          {selectedDraft.status.replace('_', ' ')}
                        </span>
                        {selectedDraft.autoPilotEligible && (
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-violet-100 text-violet-700 flex items-center gap-1">
                            <Zap className="h-3 w-3" /> auto-pilot eligible
                          </span>
                        )}
                        {selectedDraft.confidence != null && (
                          <span className="text-xs text-muted-foreground">
                            {Math.round(selectedDraft.confidence * 100)}% confidence
                          </span>
                        )}
                      </div>
                    </div>
                    {selectedDraft.summary && (
                      <p className="text-xs text-muted-foreground mt-1 italic">{selectedDraft.summary}</p>
                    )}
                  </CardHeader>

                  <CardContent className="pt-4">
                    <div className="space-y-4">
                      {/* Conversation Thread */}
                      <ConversationThread draft={selectedDraft} />

                      {/* Action Buttons */}
                      <div className="flex gap-2 flex-wrap pt-2 border-t">
                        {selectedDraft.status === 'pending' && (
                          <>
                            <Button size="sm" onClick={() => approveMut.mutate(selectedDraft.id)} disabled={approveMut.isPending}>
                              <CheckCircle2 className="h-4 w-4 mr-1" /> Approve
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => sendMut.mutate(selectedDraft.id)} disabled={sendMut.isPending}>
                              <Send className="h-4 w-4 mr-1" />{sendMut.isPending ? 'Sending…' : 'Send Now'}
                            </Button>
                            <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
                              onClick={() => dismissMut.mutate(selectedDraft.id)} disabled={dismissMut.isPending}>
                              <Ban className="h-4 w-4 mr-1" /> Dismiss
                            </Button>
                          </>
                        )}
                        {selectedDraft.status === 'approved' && (
                          <Button size="sm" onClick={() => sendMut.mutate(selectedDraft.id)} disabled={sendMut.isPending}>
                            <Send className="h-4 w-4 mr-1" />{sendMut.isPending ? 'Sending…' : 'Send Now'}
                          </Button>
                        )}
                        {(selectedDraft.status === 'sent' || selectedDraft.status === 'auto_sent') && (
                          <Badge className="bg-emerald-100 text-emerald-700">
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            {selectedDraft.status === 'auto_sent' ? 'Auto-Sent' : 'Sent'}
                          </Badge>
                        )}
                        {POSITIVE_CATEGORIES.includes(selectedDraft.category) && (
                          <Button size="sm" variant="outline" className="text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                            onClick={() => openCreateDeal(selectedDraft)}>
                            <DollarSign className="h-4 w-4 mr-1" />
                            {dealSuggesting && createDealOpen ? 'Analyzing…' : 'Create Deal'}
                          </Button>
                        )}
                      </div>

                      {/* Inline deal form */}
                      {createDealOpen && (
                        <Card className="border-emerald-200 bg-emerald-50/50">
                          <CardContent className="p-3 space-y-2">
                            <p className="text-xs font-medium flex items-center gap-1">
                              <Sparkles className="h-3 w-3" /> AI-Suggested Deal
                            </p>
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <Label className="text-xs">Deal Title</Label>
                                <Input className="h-8 text-sm mt-1" value={dealTitle} onChange={(e) => setDealTitle(e.target.value)} />
                              </div>
                              <div>
                                <Label className="text-xs">Value ($)</Label>
                                <Input className="h-8 text-sm mt-1" type="number" placeholder="0" value={dealValue} onChange={(e) => setDealValue(e.target.value)} />
                              </div>
                            </div>
                            {dealNotes && (
                              <div>
                                <Label className="text-xs">AI Notes</Label>
                                <p className="text-xs text-muted-foreground mt-1 bg-white rounded p-2 border">{dealNotes}</p>
                              </div>
                            )}
                            {dealNextAction && (
                              <div>
                                <Label className="text-xs">Suggested Next Action</Label>
                                <p className="text-xs text-emerald-800 mt-1 bg-white rounded p-2 border border-emerald-200">{dealNextAction}</p>
                              </div>
                            )}
                            <div className="flex gap-2">
                              <Button size="sm" disabled={!dealTitle || createDealMut.isPending}
                                onClick={() => createDealMut.mutate({ title: dealTitle, value: parseFloat(dealValue) || 0, stage: 'qualified', notes: dealNotes || undefined, prospectId: selectedDraft?.prospectId, source: 'cold_email' })}>
                                {createDealMut.isPending ? 'Creating…' : 'Create Deal'}
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setCreateDealOpen(false)}>Cancel</Button>
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </CardContent>
                </>
              )}
            </Card>
          </div>

          {/* Workflow info card */}
          <Card className="border-blue-100 bg-blue-50/50">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
                <div className="text-xs text-blue-800 space-y-1">
                  <p className="font-medium">Auto-Draft Reply Workflow</p>
                  <p>When a prospect replies to your email: 1) Go to <b>Campaigns &gt; Sequences</b> and click the reply categorize button on a replied sequence. 2) AI categorizes the intent and generates a draft response. 3) Review, approve, and send — nothing goes out without your approval.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Auto-Pilot Tab ─────────────────────────────────────────────── */}
        <TabsContent value="autopilot" className="space-y-4 mt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="border-violet-200 bg-violet-50/30">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-violet-700"><Zap className="h-4 w-4" /><span className="text-xs font-medium">Eligible</span></div>
                <p className="text-2xl font-bold mt-1">{autoPilotStats.eligible}</p>
                <p className="text-[11px] text-muted-foreground">Pending + auto-pilot eligible</p>
              </CardContent>
            </Card>
            <Card className="border-emerald-200 bg-emerald-50/30">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="h-4 w-4" /><span className="text-xs font-medium">Auto-Sent</span></div>
                <p className="text-2xl font-bold mt-1">{autoPilotStats.autoSent}</p>
                <p className="text-[11px] text-muted-foreground">Already sent via Auto-Pilot</p>
              </CardContent>
            </Card>
            <Card className="border-amber-200 bg-amber-50/30">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-amber-700"><Clock className="h-4 w-4" /><span className="text-xs font-medium">Pending Review</span></div>
                <p className="text-2xl font-bold mt-1">{autoPilotStats.pendingReview}</p>
                <p className="text-[11px] text-muted-foreground">All drafts awaiting your action</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-muted-foreground"><MessageCircleReply className="h-4 w-4" /><span className="text-xs font-medium">Total Drafts</span></div>
                <p className="text-2xl font-bold mt-1">{autoPilotStats.total}</p>
                <p className="text-[11px] text-muted-foreground">All reply drafts</p>
              </CardContent>
            </Card>
          </div>

          <Card className="border-violet-200 bg-gradient-to-br from-violet-50/60 to-white">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><Bot className="h-4 w-4 text-violet-600" /> Auto-Pilot Reply Sender</CardTitle>
              <CardDescription>
                Auto-send high-confidence positive replies. Drafts with category <code className="text-[10px] bg-muted px-1 py-0.5 rounded">interested</code>, <code className="text-[10px] bg-muted px-1 py-0.5 rounded">meeting_request</code>, <code className="text-[10px] bg-muted px-1 py-0.5 rounded">positive</code> with confidence ≥ 80% are eligible.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={handlePreviewAutoPilot} disabled={apPreviewLoading}>
                  {apPreviewLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Eye className="h-4 w-4 mr-1.5" />}
                  Preview Auto-Pilot
                </Button>
                <Button className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white"
                  onClick={() => { if (autoPilotStats.eligible === 0) { toast.info('No eligible drafts to auto-send.'); return; } setApConfirmOpen(true); }}
                  disabled={apSending}>
                  {apSending ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Send className="h-4 w-4 mr-1.5" />}
                  Run Auto-Pilot ({autoPilotStats.eligible} draft{autoPilotStats.eligible === 1 ? '' : 's'})
                </Button>
              </div>
              {apSending && (
                <div className="rounded-md bg-violet-50 border border-violet-200 p-3 text-xs text-violet-800 flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Auto-Pilot is sending eligible drafts via MailBridge…
                </div>
              )}
              <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-xs text-blue-800 space-y-1">
                <p className="font-medium flex items-center gap-1.5"><Info className="h-3.5 w-3.5" /> How Auto-Pilot works</p>
                <ol className="list-decimal list-inside space-y-0.5 ml-1">
                  <li>Click <b>Preview Auto-Pilot</b> to dry-run — see exactly which drafts would be sent.</li>
                  <li>Click <b>Run Auto-Pilot</b> to actually send. You'll get a confirmation dialog first.</li>
                  <li>If MailBridge is connected, drafts are sent via your sending domain. Otherwise, drafts are marked <code className="text-[10px] bg-white px-1 py-0.5 rounded">auto_sent</code> but not delivered.</li>
                  <li>Failed sends stay in <code className="text-[10px] bg-white px-1 py-0.5 rounded">pending</code> so you can retry manually.</li>
                </ol>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Log a Reply Dialog */}
      <Dialog open={logOpen} onOpenChange={setLogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Log a Reply</DialogTitle>
            <DialogDescription>Paste an external reply that wasn't captured by MailBridge.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Prospect <span className="text-destructive">*</span></Label>
              <Select value={logProspectId} onValueChange={(v) => { setLogProspectId(v); setLogSequenceId(''); }}>
                <SelectTrigger><SelectValue placeholder="Select prospect…" /></SelectTrigger>
                <SelectContent className="max-h-64">
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName}{p.company ? ` — ${p.company}` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Sequence (Touch) <span className="text-destructive">*</span></Label>
              <Select value={logSequenceId} onValueChange={setLogSequenceId} disabled={!logProspectId}>
                <SelectTrigger><SelectValue placeholder={logProspectId ? 'Select sequence…' : 'Select a prospect first'} /></SelectTrigger>
                <SelectContent className="max-h-64">
                  {logSequences.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      Touch {s.touchNumber} — {s.angle.replace(/_/g, ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Reply Text <span className="text-destructive">*</span></Label>
              <Textarea rows={5} value={logReplyText} onChange={(e) => setLogReplyText(e.target.value)} placeholder="Paste the prospect's reply here…" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLogOpen(false)}>Cancel</Button>
            <Button disabled={!logReplyText.trim() || !logProspectId || !logSequenceId || logSubmitting} onClick={handleLogReply}>
              {logSubmitting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} Log Reply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Auto-Pilot Preview Dialog */}
      <Dialog open={apPreviewOpen} onOpenChange={setApPreviewOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Eye className="h-4 w-4 text-violet-600" /> Auto-Pilot Preview (Dry-Run)</DialogTitle>
            <DialogDescription>
              {apPreviewLoading ? 'Loading…' : `${apPreview?.count ?? 0} draft${(apPreview?.count ?? 0) === 1 ? '' : 's'} would be sent.`}
            </DialogDescription>
          </DialogHeader>
          {apPreviewLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
          ) : (
            <div className="max-h-72 overflow-y-auto space-y-2">
              {(apPreview?.eligible ?? []).length === 0
                ? <p className="text-sm text-muted-foreground text-center py-4">No eligible drafts.</p>
                : (apPreview?.eligible ?? []).map((d) => (
                  <div key={d.id} className="p-3 rounded-lg border text-sm space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', CATEGORY_COLORS[d.category] ?? 'bg-gray-100')}>
                          {d.category.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs font-medium">{d.prospectName ?? d.prospectEmail ?? 'Unknown'}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{d.confidence != null ? `${Math.round(d.confidence * 100)}% confidence` : ''}</span>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2">{d.draftBody ?? d.originalReply}</p>
                  </div>
                ))
              }
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setApPreviewOpen(false)}>Close</Button>
            <Button onClick={() => { setApPreviewOpen(false); setApConfirmOpen(true); }} disabled={(apPreview?.count ?? 0) === 0}>
              Proceed to Send All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Auto-Pilot Confirm Dialog */}
      <Dialog open={apConfirmOpen} onOpenChange={setApConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-amber-600" /> Confirm Auto-Pilot Send</DialogTitle>
            <DialogDescription>
              This will send <strong>{autoPilotStats.eligible}</strong> eligible draft{autoPilotStats.eligible === 1 ? '' : 's'} via MailBridge. Cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApConfirmOpen(false)}>Cancel</Button>
            <Button className="bg-violet-600 hover:bg-violet-700 text-white" onClick={handleRunAutoPilot} disabled={apSending}>
              {apSending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />} Run Auto-Pilot
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Auto-Pilot Result Dialog */}
      <Dialog open={apResultOpen} onOpenChange={setApResultOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {(apResult?.failed ?? 0) === 0 ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-red-600" />}
              Auto-Pilot Results
            </DialogTitle>
            <DialogDescription>Send run complete.</DialogDescription>
          </DialogHeader>
          {apResult && (
            <div className="grid grid-cols-3 gap-4 py-2">
              {[
                { label: 'Sent', value: apResult.sent, color: 'text-emerald-600' },
                { label: 'Failed', value: apResult.failed, color: 'text-red-600' },
                { label: 'Total', value: apResult.total, color: 'text-foreground' },
              ].map((s) => (
                <div key={s.label} className="text-center p-3 rounded-lg border">
                  <p className={cn('text-2xl font-bold', s.color)}>{s.value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
                </div>
              ))}
            </div>
          )}
          <DialogFooter><Button onClick={() => setApResultOpen(false)}>Done</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
