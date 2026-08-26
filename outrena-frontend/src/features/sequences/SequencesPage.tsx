// import { useState, useCallback } from 'react';
// import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
// import {
//   Layers, Loader2, Copy, FileDown, FileText,
//   ChevronDown, ChevronUp, Send, AlertCircle, Clock,
//   LayoutTemplate, Wand2, RefreshCw, Bot, PenLine,
// } from 'lucide-react';
// import { Button } from '@/components/ui/button';
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
// import { Input } from '@/components/ui/input';
// import { Label } from '@/components/ui/label';
// import { Textarea } from '@/components/ui/textarea';
// import { Badge } from '@/components/ui/badge';
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
// import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
// import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// import { toast } from 'sonner';
// import { http } from '@/services/apiClient';
// import { useAuth } from '@/context/AuthContext';
 
// // ─── Types ───────────────────────────────────────────────────────────────────
 
// interface Campaign {
//   id: string;
//   name: string;
//   llmConfigId?: string | null;
//   icpProfileId?: string | null;
//   framework?: string | null;
//   senderRole?: string | null;
//   senderCompany?: string | null;
//   senderOffer?: string | null;
//   proofMetric?: string | null;
// }
 
// interface Prospect {
//   id: string;
//   firstName: string;
//   lastName: string;
//   title?: string | null;
//   company?: string | null;
//   seniority?: string;
//   signals?: string | null;
//   icpProfileId?: string | null;
// }
 
// interface Sequence {
//   id: string;
//   campaignId: string;
//   prospectId: string;
//   touchNumber: number;
//   sendDay: number;
//   angle: string;
//   framework: string;
//   channel: string;
//   subjectLine: string | null;
//   bodyCopy: string | null;
//   qaScore?: number | null;
//   status: string;
//   personalisationConfidence?: number | null;
//   flagForManualReview?: boolean;
//   sentAt?: string | null;
// }
 
// interface EmailTemplateResponse {
//   id: string;
//   name: string;
//   category: string;
//   framework: string | null;
//   subjectTemplate: string | null;
//   bodyTemplate: string;
//   variables: string[];
//   isShared: boolean;
//   createdAt: string;
//   updatedAt: string;
// }

// type TemplateSendMode = 'manual' | 'llm';

// // ─── Constants ────────────────────────────────────────────────────────────────
 
// const WORD_LIMITS: Record<string, number> = {
//   FirstTouch: 150, NewEvidence: 120, DifferentPain: 120,
//   IndustryInsight: 120, DirectQuestion: 80, Breakup: 60,
// };
 
// const TOUCH_INFO = [
//   { touch: 1, day: 'Day 1',  angle: 'First Touch',       words: 150, color: 'border-blue-200',    desc: 'The opener. References a specific signal or trigger event. Establishes relevance immediately — no generic intros.' },
//   { touch: 2, day: 'Day 3',  angle: 'New Evidence',      words: 120, color: 'border-cyan-200',    desc: 'Follows up with a new data point or case study. Introduces social proof or a metric the prospect cares about.' },
//   { touch: 3, day: 'Day 7',  angle: 'Different Pain',    words: 120, color: 'border-teal-200',    desc: 'Pivots to address a different pain point. Each email must work standalone — no "as I mentioned" references.' },
//   { touch: 4, day: 'Day 12', angle: 'Industry Insight',  words: 120, color: 'border-emerald-200', desc: 'Shares a relevant industry trend or benchmark. Creates FOMO about what competitors are doing differently.' },
//   { touch: 5, day: 'Day 18', angle: 'Direct Question',   words: 80,  color: 'border-amber-200',   desc: 'Short, direct question that demands a response. Example: "Is this still a priority for Q3?" Max 80 words.' },
//   { touch: 6, day: 'Day 24', angle: 'Breakup',           words: 60,  color: 'border-rose-200',    desc: 'The "breakup" email. Polite sign-off that creates urgency. Often gets the highest reply rate. Max 60 words.' },
//   { touch: 7, day: 'Day 30', angle: 'Breakup (LinkedIn)', words: 60, color: 'border-pink-200',    desc: 'LinkedIn follow-up breakup. Same tone, adapted for the LinkedIn channel.' },
// ];
 
// const STATUS_COLORS: Record<string, string> = {
//   Draft:     'bg-muted text-muted-foreground',
//   QaPassed:  'bg-emerald-100 text-emerald-700 border-emerald-200',
//   Sent:      'bg-blue-100 text-blue-700 border-blue-200',
//   Scheduled: 'bg-amber-100 text-amber-700 border-amber-200',
// };
 
// // ─── Helper ───────────────────────────────────────────────────────────────────
 
// function normalise<T>(data: unknown): T[] {
//   if (!data) return [];
//   if (Array.isArray(data)) return data as T[];
//   const p = data as { items?: T[] };
//   return Array.isArray(p.items) ? p.items : [];
// }
 
// function parseSignals(signals: string | null | undefined): unknown[] {
//   try { return signals ? (JSON.parse(signals) as unknown[]) : []; }
//   catch { return []; }
// }
 
// function wordCount(text: string | null | undefined): number {
//   return (text ?? '').split(/\s+/).filter(Boolean).length;
// }
 
// // ─── Inline Tooltip Button ────────────────────────────────────────────────────
 
// function TBtn({
//   children, tooltip, disabled, onClick, size = 'sm', variant = 'outline', className = '',
// }: {
//   children: React.ReactNode; tooltip: string; disabled?: boolean;
//   onClick?: () => void; size?: 'sm' | 'default';
//   variant?: 'outline' | 'default' | 'ghost'; className?: string;
// }) {
//   return (
//     <Tooltip>
//       <TooltipTrigger asChild>
//         <Button size={size} variant={variant} disabled={disabled} onClick={onClick} className={className}>
//           {children}
//         </Button>
//       </TooltipTrigger>
//       <TooltipContent>{tooltip}</TooltipContent>
//     </Tooltip>
//   );
// }
 
// // ─── Component ────────────────────────────────────────────────────────────────
 
// export function SequencesPage() {
//   // ── Auth / profile ───────────────────────────────────────────────────────
//   const { profile } = useAuth();
 
//   // ── Server state ────────────────────────────────────────────────────────
//   const { data: campaignsRaw, isLoading: cLoading } = useQuery({
//     queryKey: ['campaigns', { page: 1, pageSize: 100 }],
//     queryFn: () => http.get<unknown>('/api/v1/campaigns', { page: 1, page_size: 100 }),
//     staleTime: 30_000,
//   });
//   const { data: prospectsRaw } = useQuery({
//     queryKey: ['prospects', { page: 1, pageSize: 200 }],
//     queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
//     staleTime: 30_000,
//   });
 
//   const campaigns = normalise<Campaign>(campaignsRaw);
//   const prospects = normalise<Prospect>(prospectsRaw);

//   // ── Template list for the Template-Send tab ──────────────────────────────
//   const { data: templates = [], isLoading: tplLoading } = useQuery<EmailTemplateResponse[]>({
//     queryKey: ['templates'],
//     queryFn: () => http.get<EmailTemplateResponse[]>('/api/v1/templates'),
//     staleTime: 60_000,
//   });

//   // ── ICP profile list for the Template-Send tab ───────────────────────────
//   const { data: icpProfiles = [], isLoading: icpLoading } = useQuery<{ id: string; name: string }[]>({
//     queryKey: ['icp-profiles'],
//     queryFn: () => http.get<{ id: string; name: string }[]>('/api/v1/icp-profiles'),
//     staleTime: 60_000,
//   });

//   // ── Template-send mutation ───────────────────────────────────────────────
//   const templateSendMut = useMutation({
//     mutationFn: (payload: {
//       campaignId: string;
//       icpProfileId: string;
//       templateId: string;
//       mode: TemplateSendMode;
//       senderName: string;
//       senderCompany: string;
//     }) =>
//       http.post<{ mode: string; templateName: string; sequences: Sequence[]; message: string; prospectMap: Record<string, string> }>(
//         '/api/v1/sequences/template-send',
//         payload,
//       ),
//     onSuccess: (data) => {
//       setTplSequences(data.sequences);
//       setTplProspectMap(data.prospectMap ?? {});
//       toast.success(data.message);
//     },
//     onError: (err: unknown) => {
//       const detail =
//         (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
//       toast.error(detail ?? (err instanceof Error ? err.message : 'Template send failed'));
//     },
//   });
 
//   const qc = useQueryClient();

//   // ── UI state ────────────────────────────────────────────────────────────
//   const [selectedCampaignId, setSelectedCampaignId] = useState('');
//   const [selectedProspectId, setSelectedProspectId] = useState('');
//   const [framework, setFramework]                   = useState('trigger');
//   const [generating, setGenerating]                 = useState(false);
//   const [sequences, setSequences]                   = useState<Sequence[]>([]);
//   const [savingId, setSavingId]                     = useState<string | null>(null);
//   const [sendingId, setSendingId]                   = useState<string | null>(null);
//   const [showExplain, setShowExplain]               = useState(false);
//   const [exportingCsv, setExportingCsv]             = useState(false);

//   // ── Template-Send tab state ──────────────────────────────────────────────
//   const [tplCampaignId, setTplCampaignId]           = useState('');
//   const [tplIcpId, setTplIcpId]                      = useState('');
//   const [tplTemplateId, setTplTemplateId]            = useState('');
//   const [tplMode, setTplMode]                        = useState<TemplateSendMode>('manual');
//   const [tplSequences, setTplSequences]              = useState<Sequence[]>([]);
//   const [tplProspectMap, setTplProspectMap]          = useState<Record<string, string>>({});
//   const [approvingAll, setApprovingAll]              = useState(false);
 
//   // ── Derived ─────────────────────────────────────────────────────────────
//   const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) ?? null;
//   const selectedProspect = prospects.find((p) => p.id === selectedProspectId) ?? null;
 
//   // ── Handlers ──────────────────────────────────────────────────────────────
 
//   const handleGenerate = useCallback(async () => {
//     if (!selectedCampaignId || !selectedProspectId) {
//       toast.error('Select a campaign and prospect first');
//       return;
//     }
//     setGenerating(true);
//     setSequences([]);
//     try {
//       await http.post('/api/v1/campaigns/campaign-prospects', {
//         campaignId:  selectedCampaignId,
//         prospectIds: [selectedProspectId],
//         action:      'add',
//       }).catch(() => {});
 
//       await http.post(
//         `/api/v1/campaigns/${selectedCampaignId}/generate-sequences`,
//         {
//           prospectId:    selectedProspectId,
//           framework,
//           llmConfigId:   selectedCampaign?.llmConfigId ?? null,
//           senderRole:    selectedCampaign?.senderRole,
//           senderCompany: selectedCampaign?.senderCompany ?? profile?.senderCompany,
//           senderOffer:   selectedCampaign?.senderOffer   ?? profile?.senderOffer,
//           proofMetric:   selectedCampaign?.proofMetric,
//           seniority:     selectedProspect?.seniority,
//           signals:       parseSignals(selectedProspect?.signals),
//           senderFirstName: profile?.firstName  ?? undefined,
//           senderLastName:  profile?.lastName   ?? undefined,
//           senderTitle:     profile?.senderTitle ?? undefined,
//           senderSignature: profile?.emailSignature ?? undefined,
//           unsubscribeUrl:  '{{unsubscribe_url}}',
//           physicalAddress: profile?.physicalAddress ?? undefined,
//         },
//       );
 
//       const fetched = await http.get<unknown>(
//         '/api/v1/sequences',
//         { campaign_id: selectedCampaignId, prospect_id: selectedProspectId, limit: 50 },
//       );
//       const seqs: Sequence[] = Array.isArray(fetched)
//         ? fetched
//         : ((fetched as { items?: Sequence[] }).items ?? []);
 
//       if (seqs.length === 0) {
//         const all = await http.get<unknown>(
//           '/api/v1/sequences',
//           { campaign_id: selectedCampaignId, limit: 50 },
//         );
//         const allSeqs: Sequence[] = Array.isArray(all)
//           ? all
//           : ((all as { items?: Sequence[] }).items ?? []);
//         const forProspect = allSeqs.filter((s) => s.prospectId === selectedProspectId);
//         setSequences(forProspect);
//         toast.success(
//           forProspect.length > 0
//             ? `${forProspect.length} sequences loaded`
//             : 'Sequences generated — check back shortly'
//         );
//       } else {
//         setSequences(seqs);
//         toast.success(`${seqs.length}-touch sequence generated`);
//       }
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Generation failed');
//     } finally { setGenerating(false); }
//   }, [selectedCampaignId, selectedProspectId, framework, selectedCampaign, selectedProspect, profile]);
 
//   // const handleSave = useCallback(async (seq: Sequence) => {
//   //   setSavingId(seq.id);
//   //   try {
//   //     await http.put(`/api/v1/sequences/${seq.id}`, {
//   //       subjectLine: seq.subjectLine,
//   //       bodyCopy:    seq.bodyCopy,
//   //       status:      seq.status === 'Draft' ? 'Draft' : seq.status,
//   //     });
//   //     toast.success(`Touch ${seq.touchNumber} saved`);
//   //   } catch (err: unknown) {
//   //     toast.error(err instanceof Error ? err.message : 'Save failed');
//   //   } finally { setSavingId(null); }
//   // }, []);
 
//   // FIX: Approve now also calls /scheduled-send so the APScheduler picks up
//   // the sequence automatically. Without this, sequences stayed in QaPassed
//   // forever and the scheduler (which only queries status=Scheduled) never
//   // had anything to send.
//   const handleApprove = useCallback(async (seq: Sequence, index: number) => {
//     const wc = wordCount(seq.bodyCopy);
//     const limit = WORD_LIMITS[seq.angle] ?? 150;
//     if (wc > limit) {
//       toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit (${wc} words)`);
//       return;
//     }
//     setSavingId(seq.id);
//     try {
//       await http.put(`/api/v1/sequences/${seq.id}`, {
//         subjectLine: seq.subjectLine,
//         bodyCopy:    seq.bodyCopy,
//         status:      'QaPassed',
//       });
//       // Move to Scheduled so the APScheduler tick picks it up automatically.
//       await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
//       const updated = [...sequences];
//       updated[index] = { ...updated[index], status: 'Scheduled' };
//       setSequences(updated);
//       toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Approve failed');
//     } finally { setSavingId(null); }
//   }, [sequences]);
 
//   // FIX: Approve All also schedules every touch in one pass.
//   const handleApproveAll = useCallback(async () => {
//     for (let i = 0; i < sequences.length; i++) {
//       const seq = sequences[i];
//       const wc = wordCount(seq.bodyCopy);
//       const limit = WORD_LIMITS[seq.angle] ?? 150;
//       if (wc > limit) {
//         toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit — fix before approving all`);
//         return;
//       }
//     }
//     setSavingId('all');
//     try {
//       // Step 1: set all to QaPassed
//       await Promise.all(
//         sequences.map((seq) =>
//           http.put(`/api/v1/sequences/${seq.id}`, {
//             subjectLine: seq.subjectLine,
//             bodyCopy:    seq.bodyCopy,
//             status:      'QaPassed',
//           })
//         )
//       );
//       // Step 2: move all to Scheduled so the APScheduler picks them up.
//       await Promise.all(
//         sequences.map((seq) =>
//           http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {})
//         )
//       );
//       setSequences(sequences.map((s) => ({ ...s, status: 'Scheduled' })));
//       toast.success('All touches approved & scheduled');
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Approve all failed');
//     } finally { setSavingId(null); }
//   }, [sequences]);
 
//   const handleSendNow = useCallback(async (seq: Sequence, index: number) => {
//     setSendingId(seq.id);
//     try {
//       await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
//       const updated = [...sequences];
//       updated[index] = { ...updated[index], status: 'Sent' };
//       setSequences(updated);
//       toast.success(`Touch ${seq.touchNumber} sent`);
//     } catch (err: unknown) {
//       // Extract FastAPI detail string (warming gate, DNS gate, etc.) if present.
//       // AxiosError.message is generic ("Request failed with status 422") — the
//       // actual human-readable reason is in error.response.data.detail.
//       const detail =
//         (err as { response?: { data?: { detail?: string } } })
//           ?.response?.data?.detail;
//       toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
//     } finally { setSendingId(null); }
//   }, [sequences]);

//   // ── Tab 2 handlers — identical logic but operate on tplSequences ──────────
//   // const handleTplSave = useCallback(async (seq: Sequence) => {
//   //   setSavingId(seq.id);
//   //   try {
//   //     await http.put(`/api/v1/sequences/${seq.id}`, {
//   //       subjectLine: seq.subjectLine,
//   //       bodyCopy:    seq.bodyCopy,
//   //       status:      seq.status === 'Draft' ? 'Draft' : seq.status,
//   //     });
//   //     toast.success(`Touch ${seq.touchNumber} saved`);
//   //   } catch (err: unknown) {
//   //     toast.error(err instanceof Error ? err.message : 'Save failed');
//   //   } finally { setSavingId(null); }
//   // }, []);

//   const handleTplApprove = useCallback(async (seq: Sequence, index: number) => {
//     setSavingId(seq.id);
//     try {
//       await http.put(`/api/v1/sequences/${seq.id}`, {
//         subjectLine: seq.subjectLine,
//         bodyCopy:    seq.bodyCopy,
//         status:      'QaPassed',
//       });
//       await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
//       const updated = [...tplSequences];
//       updated[index] = { ...updated[index], status: 'Scheduled' };
//       setTplSequences(updated);
//       toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Approve failed');
//     } finally { setSavingId(null); }
//   }, [tplSequences]);

//   const handleTplSendNow = useCallback(async (seq: Sequence, index: number) => {
//     setSendingId(seq.id);
//     try {
//       await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
//       const updated = [...tplSequences];
//       updated[index] = { ...updated[index], status: 'Sent' };
//       setTplSequences(updated);
//       toast.success(`Touch ${seq.touchNumber} sent`);
//     } catch (err: unknown) {
//       const detail =
//         (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
//       toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
//     } finally { setSendingId(null); }
//   }, [tplSequences]);

//   // ── Approve All & Schedule All for Tab 2 ────────────────────────────────
//   // Runs sequentially (not Promise.all) to avoid asyncpg prepared-statement
//   // cache collisions on the schema-per-tenant search_path switching.
//   const handleTplApproveAll = useCallback(async () => {
//     const pending = tplSequences.filter((s) => s.status !== 'Scheduled' && s.status !== 'Sent');
//     if (pending.length === 0) {
//       toast.info('All touches are already scheduled or sent.');
//       return;
//     }
//     setApprovingAll(true);
//     let approved = 0;
//     const updated = [...tplSequences];
//     try {
//       for (const seq of pending) {
//         await http.put(`/api/v1/sequences/${seq.id}`, {
//           subjectLine: seq.subjectLine,
//           bodyCopy:    seq.bodyCopy,
//           status:      'QaPassed',
//         });
//         await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
//         const idx = updated.findIndex((s) => s.id === seq.id);
//         if (idx !== -1) updated[idx] = { ...updated[idx], status: 'Scheduled' };
//         approved++;
//       }
//       setTplSequences([...updated]);
//       toast.success(`${approved} email${approved !== 1 ? 's' : ''} approved & scheduled`);
//     } catch (err: unknown) {
//       const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
//       toast.error(detail ?? (err instanceof Error ? err.message : 'Approve all failed'));
//       setTplSequences([...updated]); // persist partial progress
//     } finally { setApprovingAll(false); }
//   }, [tplSequences]);

//   const handleExportCsv = useCallback(async () => {
//     if (!selectedCampaignId) { toast.error('Select a campaign first'); return; }
//     setExportingCsv(true);
//     try {
//       const rows = sequences.length > 0
//         ? sequences
//         : await http.get<Sequence[]>('/api/v1/sequences/export', {
//             campaign_id: selectedCampaignId,
//           });
//       const data = Array.isArray(rows) ? rows : sequences;
//       const headers = ['touchNumber', 'sendDay', 'angle', 'channel', 'subjectLine', 'bodyCopy', 'qaScore', 'status', 'sentAt'];
//       const csv = [
//         headers.join(','),
//         ...data.map((s) =>
//           headers.map((h) => {
//             const val = String((s as unknown as Record<string, unknown>)[h] ?? '');
//             return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
//           }).join(',')
//         ),
//       ].join('\n');
//       const blob = new Blob([csv], { type: 'text/csv' });
//       const url  = URL.createObjectURL(blob);
//       const a    = document.createElement('a');
//       a.href     = url;
//       a.download = `sequences-${selectedCampaignId}-${new Date().toISOString().split('T')[0]}.csv`;
//       a.click();
//       URL.revokeObjectURL(url);
//       toast.success('CSV exported');
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Export failed');
//     } finally { setExportingCsv(false); }
//   }, [sequences, selectedCampaignId, selectedProspectId]);
 
//   // ── Render ───────────────────────────────────────────────────────────────
 
//   if (cLoading) {
//     return (
//       <div className="flex items-center justify-center h-64">
//         <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
//       </div>
//     );
//   }
 
//   return (
//     <div className="space-y-6">
//       {/* Header */}
//       <div className="flex items-center justify-between flex-wrap gap-2">
//         <div>
//           <h3 className="text-lg font-semibold">Sequence Builder</h3>
//           <p className="text-sm text-muted-foreground">
//             Generate 7-touch AI sequences or send a saved template directly
//           </p>
//         </div>
 
//         {/* Profile status indicator — shown when profile is missing fields */}
//         {(!profile?.emailSignature || !profile?.firstName) && (
//           <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
//             <AlertCircle className="h-3 w-3 shrink-0" />
//             <span>
//               Complete your{' '}
//               <a href="/settings/profile" className="underline underline-offset-2">
//                 profile &amp; signature
//               </a>{' '}
//               for personalised emails
//             </span>
//           </div>
//         )}
 
//         <div className="flex gap-2 flex-wrap">
//           <TBtn
//             variant="outline"
//             tooltip="Export sequences to CSV"
//             onClick={handleExportCsv}
//             disabled={exportingCsv || (!selectedCampaignId && sequences.length === 0)}
//           >
//             {exportingCsv
//               ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
//               : <FileDown className="h-4 w-4 mr-2" />
//             }
//             Export CSV
//           </TBtn>
//           <TBtn
//             variant="outline"
//             tooltip="How the 7-touch cadence works"
//             onClick={() => setShowExplain((v) => !v)}
//           >
//             <FileText className="h-4 w-4 mr-2" />
//             How It Works
//             {showExplain ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
//           </TBtn>
//         </div>
//       </div>
 
//       {/* ── Main Tabs ─────────────────────────────────────────────────────── */}
//       <Tabs defaultValue="ai-generate" className="space-y-6">
//         <TabsList className="grid w-full grid-cols-2 max-w-md">
//           <TabsTrigger value="ai-generate" className="flex items-center gap-2">
//             <Bot className="h-4 w-4" />
//             AI Generate
//           </TabsTrigger>
//           <TabsTrigger value="template-send" className="flex items-center gap-2">
//             <LayoutTemplate className="h-4 w-4" />
//             Manual Template
//           </TabsTrigger>
//         </TabsList>

//         {/* ── Tab 1: AI Generate (existing flow, unchanged) ─────────────── */}
//         <TabsContent value="ai-generate" className="space-y-4 mt-0">

//       {/* Configuration Card */}
//       <Card>
//         <CardContent className="p-4">
//           <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
//             <div className="space-y-2">
//               <Label>Campaign</Label>
//               <Select
//                 value={selectedCampaignId}
//                 onValueChange={(v) => { setSelectedCampaignId(v); setSequences([]); }}
//               >
//                 <SelectTrigger><SelectValue placeholder="Select campaign..." /></SelectTrigger>
//                 <SelectContent className="max-h-64">
//                   {campaigns.map((c) => (
//                     <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//               {campaigns.length === 0 && (
//                 <p className="text-xs text-amber-600">Create a campaign first</p>
//               )}
//             </div>
 
//             <div className="space-y-2">
//               <Label>Prospect</Label>
//               <Select value={selectedProspectId} onValueChange={setSelectedProspectId}>
//                 <SelectTrigger><SelectValue placeholder="Select prospect..." /></SelectTrigger>
//                 <SelectContent className="max-h-64">
//                   {prospects.map((p) => (
//                     <SelectItem key={p.id} value={p.id}>
//                       {p.firstName} {p.lastName} — {p.company || 'No company'}
//                     </SelectItem>
//                   ))}
//                 </SelectContent>
//               </Select>
//             </div>
 
//             <div className="space-y-2">
//               <Label>Framework</Label>
//               <Select value={framework} onValueChange={setFramework}>
//                 <SelectTrigger><SelectValue /></SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="trigger">Trigger-Based</SelectItem>
//                   <SelectItem value="problem">Problem-First</SelectItem>
//                   <SelectItem value="value">Value-First</SelectItem>
//                   <SelectItem value="mutual">Mutual Connection</SelectItem>
//                   <SelectItem value="direct">Direct Ask</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
 
//             <TBtn
//               size="default"
//               variant="default"
//               tooltip="Generate a 7-touch email sequence"
//               onClick={handleGenerate}
//               disabled={generating || !selectedCampaignId || !selectedProspectId}
//             >
//               {generating
//                 ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
//                 : <><Layers className="h-4 w-4 mr-2" />Generate 7-Touch Sequence</>
//               }
//             </TBtn>
//           </div>
//         </CardContent>
//       </Card>
 
//       {/* Sequence Timeline */}
//       {sequences.length > 0 && (
//         <div className="space-y-4">
//           <div className="flex items-center justify-between">
//             <h4 className="font-medium text-sm">
//               Sequence Timeline
//               <span className="ml-2 text-xs text-muted-foreground font-normal">
//                 ({sequences.filter((s) => s.status === 'Scheduled' || s.status === 'QaPassed').length}/{sequences.length} approved)
//               </span>
//             </h4>
//             {/* Approve All & Schedule — moves every touch to Scheduled in one click */}
//             <TBtn
//               size="sm"
//               variant="outline"
//               tooltip="Approve all touches and schedule for automated sending"
//               onClick={handleApproveAll}
//               disabled={savingId === 'all' || sequences.every((s) => s.status === 'Scheduled' || s.status === 'Sent')}
//             >
//               {savingId === 'all'
//                 ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
//                 : <Clock className="h-3 w-3 mr-1" />
//               }
//               Approve All &amp; Schedule
//             </TBtn>
//           </div>
 
//           <div className="relative">
//             {/* Timeline spine */}
//             <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
 
//             {sequences.map((seq, i) => {
//               const wc        = wordCount(seq.bodyCopy);
//               const limit     = WORD_LIMITS[seq.angle] ?? 150;
//               const over      = wc > limit;
//               const isSaving  = savingId === seq.id;
//               const isSending = sendingId === seq.id;
 
//               return (
//                 <div key={seq.id} className="relative pl-14 pb-6">
//                   {/* Touch number bubble */}
//                   <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
//                     seq.status === 'Scheduled'
//                       ? 'bg-amber-500 text-white'
//                       : seq.status === 'QaPassed'
//                         ? 'bg-emerald-500 text-white'
//                         : seq.status === 'Sent'
//                           ? 'bg-blue-500 text-white'
//                           : 'bg-primary text-primary-foreground'
//                   }`}>
//                     {seq.touchNumber}
//                   </div>
 
//                   <Card className={
//                     seq.status === 'Scheduled'
//                       ? 'border-amber-200'
//                       : seq.status === 'QaPassed'
//                         ? 'border-emerald-200'
//                         : ''
//                   }>
//                     <CardHeader className="pb-2">
//                       <div className="flex items-start justify-between gap-2 flex-wrap">
//                         <div>
//                           <CardTitle className="text-sm flex items-center gap-2">
//                             Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, ' $1').trim()}
//                             {seq.channel === 'LINKEDIN' && (
//                               <Badge variant="outline" className="text-[10px] bg-cyan-50 text-cyan-700 border-cyan-200">
//                                 LinkedIn
//                               </Badge>
//                             )}
//                             {seq.channel === 'EMAIL' && (
//                               <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">
//                                 Email
//                               </Badge>
//                             )}
//                             {seq.qaScore != null && (
//                               <Badge
//                                 variant="outline"
//                                 className={`text-[10px] ${
//                                   seq.qaScore >= 80
//                                     ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
//                                     : seq.qaScore >= 60
//                                       ? 'bg-amber-50 text-amber-700 border-amber-200'
//                                       : 'bg-red-50 text-red-700 border-red-200'
//                                 }`}
//                               >
//                                 QA {seq.qaScore}/100
//                               </Badge>
//                             )}
//                           </CardTitle>
//                           <CardDescription className="text-xs">Send on Day {seq.sendDay}</CardDescription>
//                         </div>
//                         <Badge
//                           variant="outline"
//                           className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
//                         >
//                           {seq.status}
//                         </Badge>
//                       </div>
 
//                       {seq.flagForManualReview && (
//                         <div className="flex items-center gap-1 text-xs text-amber-600 mt-1">
//                           <AlertCircle className="h-3 w-3 shrink-0" />
//                           <span>Low personalisation confidence — review before sending</span>
//                         </div>
//                       )}
//                     </CardHeader>
 
//                     <CardContent className="space-y-3">
//                       {/* Subject line */}
//                       <div className="space-y-1">
//                         <Label className="text-xs">Subject</Label>
//                         <Input
//                           value={seq.subjectLine ?? ''}
//                           onChange={(e) => {
//                             const updated = [...sequences];
//                             updated[i] = { ...updated[i], subjectLine: e.target.value };
//                             setSequences(updated);
//                           }}
//                           className="text-sm"
//                           placeholder="Subject line..."
//                         />
//                       </div>
 
//                       {/* Body copy */}
//                       <div className="space-y-1">
//                         <Label className="text-xs">Body</Label>
//                         <Textarea
//                           value={seq.bodyCopy ?? ''}
//                           onChange={(e) => {
//                             const updated = [...sequences];
//                             updated[i] = { ...updated[i], bodyCopy: e.target.value };
//                             setSequences(updated);
//                           }}
//                           rows={5}
//                           className="text-sm font-mono"
//                           placeholder="Email body..."
//                         />
//                         <div className="flex justify-between text-xs">
//                           <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
//                             Words: {wc} / {limit}
//                             {over && ' — OVER LIMIT'}
//                           </span>
//                           {seq.personalisationConfidence != null && (
//                             <span className="text-muted-foreground">
//                               Confidence: {Math.round(seq.personalisationConfidence * 100)}%
//                             </span>
//                           )}
//                         </div>
//                       </div>
 
//                       {/* Action buttons */}
//                       <div className="flex gap-2 flex-wrap">
//                         {/* Save */}
//                         {/* <TBtn
//                           size="sm"
//                           variant="outline"
//                           tooltip="Save subject and body edits"
//                           onClick={() => handleSave(seq)}
//                           disabled={isSaving}
//                         >
//                           {isSaving
//                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
//                             : <Save className="h-3 w-3 mr-1" />
//                           }
//                           Save
//                         </TBtn> */}
 
//                         {/* Approve & Schedule — replaces the old Approve button */}
//                         <TBtn
//                           size="sm"
//                           variant="outline"
//                           tooltip={
//                             over
//                               ? `Exceeds ${limit}-word limit`
//                               : 'Approve and schedule for automated sending'
//                           }
//                           onClick={() => handleApprove(seq, i)}
//                           disabled={isSaving || seq.status === 'Scheduled' || seq.status === 'Sent'}
//                         >
//                           <Clock className="h-3 w-3 mr-1" />
//                           {seq.status === 'Scheduled'
//                             ? 'Scheduled'
//                             : seq.status === 'Sent'
//                               ? 'Sent'
//                               : 'Approve & Schedule'
//                           }
//                         </TBtn>
 
//                         {/* Copy body */}
//                         <TBtn
//                           size="sm"
//                           variant="ghost"
//                           tooltip="Copy body to clipboard"
//                           onClick={() => {
//                             navigator.clipboard.writeText(seq.bodyCopy ?? '');
//                             toast.success('Copied');
//                           }}
//                         >
//                           <Copy className="h-3 w-3 mr-1" />
//                           Copy
//                         </TBtn>
 
//                         {/* Send Now — manual immediate send, bypasses schedule */}
//                         <TBtn
//                           size="sm"
//                           variant="ghost"
//                           tooltip="Send this touch immediately via MailBridge (bypasses schedule)"
//                           onClick={() => handleSendNow(seq, i)}
//                           disabled={isSending || seq.status === 'Sent'}
//                         >
//                           {isSending
//                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
//                             : <Send className="h-3 w-3 mr-1" />
//                           }
//                           {seq.status === 'Sent' ? 'Sent' : 'Send Now'}
//                         </TBtn>
//                       </div>
//                     </CardContent>
//                   </Card>
//                 </div>
//               );
//             })}
//           </div>
//         </div>
//       )}
 
//       {/* Empty state */}
//       {sequences.length === 0 && !generating && (
//         <div className="py-16 text-center text-muted-foreground">
//           <Layers className="h-12 w-12 mx-auto mb-4 opacity-30" />
//           <p className="text-sm">Select a campaign and prospect, then click Generate</p>
//           <p className="text-xs mt-1">Creates 7 personalised touches across ~30 days</p>
//         </div>
//       )}
 
//       {/* Cadence Reference Guide */}
//       {showExplain && (
//         <Card id="seq-explain" className="border-blue-100 bg-blue-50/30">
//           <CardHeader className="pb-3">
//             <CardTitle className="text-sm flex items-center gap-2">
//               <FileText className="h-4 w-4" />
//               How the 7-Touch Sequence Works
//             </CardTitle>
//           </CardHeader>
//           <CardContent className="space-y-4 text-sm">
//             <p className="text-muted-foreground">
//               A scientifically-structured cold email cadence designed to maximise reply rates through
//               strategic escalation. Each touch uses a different psychological angle sent at an optimised
//               interval.
//             </p>
 
//             <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
//               {TOUCH_INFO.map((t) => (
//                 <div key={t.touch} className={`p-3 rounded-lg border ${t.color} space-y-1`}>
//                   <div className="flex items-center justify-between">
//                     <span className="font-medium text-sm">Touch {t.touch}: {t.angle}</span>
//                     <span className="text-xs text-muted-foreground">{t.day}</span>
//                   </div>
//                   <p className="text-xs text-muted-foreground">{t.desc}</p>
//                   <p className="text-xs font-medium">{t.words} words max</p>
//                 </div>
//               ))}
//             </div>
 
//             <div className="bg-muted rounded-lg p-3 text-xs space-y-1">
//               <p className="font-medium">Key Principles:</p>
//               <ul className="list-disc list-inside space-y-1 text-muted-foreground">
//                 <li><strong>Standalone Rule:</strong> Each email must make sense if read in isolation</li>
//                 <li><strong>Escalating Urgency:</strong> Tone gradually increases from helpful to direct</li>
//                 <li><strong>Peer Test:</strong> Must read like an internal message, not marketing copy</li>
//                 <li><strong>Word Limits:</strong> Enforced by angle (see cards above) and seniority tier</li>
//                 <li><strong>No "Checking In":</strong> Banned: "circling back", "just wanted to follow up", "touching base"</li>
//               </ul>
//             </div>
//           </CardContent>
//         </Card>
//       )}

//         </TabsContent>
//         {/* ── End Tab 1 ───────────────────────────────────────────────────── */}

//         {/* ── Tab 2: Template Send ──────────────────────────────────────── */}
//         <TabsContent value="template-send" className="space-y-4 mt-0">

//           {/* Explainer */}
//           <Card className="border-violet-100 bg-violet-50/40">
//             <CardContent className="p-4">
//               <div className="flex items-start gap-3">
//                 <LayoutTemplate className="h-4 w-4 text-violet-600 mt-0.5 shrink-0" />
//                 <div className="space-y-2 text-xs">
//                   <p className="font-medium text-violet-900">How Template Send works</p>
//                   <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
//                     <div className="flex items-start gap-2">
//                       <PenLine className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
//                       <div>
//                         <p className="font-medium text-violet-800">Manual</p>
//                         <p className="text-violet-700">
//                           Select an ICP profile — the template renders for <strong>every prospect</strong> linked
//                           to that ICP. Variables like name, company, and title are substituted per prospect.
//                           Signature and unsubscribe footer are injected by MailBridge at send time.
//                         </p>
//                       </div>
//                     </div>
//                     <div className="flex items-start gap-2">
//                       <Wand2 className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
//                       <div>
//                         <p className="font-medium text-violet-800">LLM-Assisted</p>
//                         <p className="text-violet-700">
//                           The AI generates 7 personalised touches per prospect under the ICP,
//                           using your template's structure and offer as a guide.
//                         </p>
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               </div>
//             </CardContent>
//           </Card>

//           {/* Configuration card */}
//           <Card>
//             <CardContent className="p-4 space-y-4">
//               <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-start">

//                 {/* Campaign selector */}
//                 <div className="space-y-1.5">
//                   <Label className="text-xs font-medium text-muted-foreground">Campaign</Label>
//                   <Select
//                     value={tplCampaignId}
//                     onValueChange={(v) => { setTplCampaignId(v); setTplSequences([]); }}
//                   >
//                     <SelectTrigger className="w-full"><SelectValue placeholder="Select campaign..." /></SelectTrigger>
//                     <SelectContent className="max-h-64">
//                       {campaigns.map((c) => (
//                         <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
//                       ))}
//                     </SelectContent>
//                   </Select>
//                   {campaigns.length === 0 && (
//                     <p className="text-xs text-amber-600">Create a campaign first</p>
//                   )}
//                 </div>

//                 {/* ICP Profile selector */}
//                 <div className="space-y-1.5">
//                   <Label className="text-xs font-medium text-muted-foreground">ICP Profile</Label>
//                   {icpLoading ? (
//                     <div className="h-9 rounded-md border bg-muted animate-pulse" />
//                   ) : (
//                     <Select
//                       value={tplIcpId}
//                       onValueChange={(v) => { setTplIcpId(v); setTplSequences([]); }}
//                     >
//                       <SelectTrigger className="w-full">
//                         <SelectValue placeholder="Select ICP profile..." />
//                       </SelectTrigger>
//                       <SelectContent className="max-h-64">
//                         {icpProfiles.map((icp) => (
//                           <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>
//                         ))}
//                       </SelectContent>
//                     </Select>
//                   )}
//                   {icpProfiles.length === 0 && !icpLoading && (
//                     <p className="text-xs text-amber-600">
//                       No ICP profiles yet —{' '}
//                       <a href="/icp" className="underline underline-offset-2">create one</a>
//                     </p>
//                   )}
//                 </div>

//                 {/* Template selector */}
//                 <div className="space-y-1.5">
//                   <Label className="text-xs font-medium text-muted-foreground">Template</Label>
//                   {tplLoading ? (
//                     <div className="h-9 rounded-md border bg-muted animate-pulse" />
//                   ) : (
//                     <Select value={tplTemplateId} onValueChange={setTplTemplateId}>
//                       <SelectTrigger className="w-full">
//                         <SelectValue placeholder="Select template..." />
//                       </SelectTrigger>
//                       <SelectContent className="max-h-64">
//                         {templates.map((t) => (
//                           <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
//                         ))}
//                       </SelectContent>
//                     </Select>
//                   )}
//                   {templates.length === 0 && !tplLoading && (
//                     <p className="text-xs text-amber-600">
//                       No templates yet —{' '}
//                       <a href="/templates" className="underline underline-offset-2">create one</a>
//                     </p>
//                   )}
//                 </div>
//               </div>

//               {/* ICP helper text — below grid so it doesn't affect dropdown alignment */}
//               {tplIcpId && (
//                 <p className="text-xs text-muted-foreground -mt-2">
//                   The template will render for all prospects linked to this ICP
//                 </p>
//               )}

//               {/* Mode toggle */}
//               <div className="space-y-2">
//                 <Label>Generation mode</Label>
//                 <div className="flex gap-2 flex-wrap">
//                   <button
//                     type="button"
//                     onClick={() => setTplMode('manual')}
//                     className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
//                       tplMode === 'manual'
//                         ? 'bg-violet-600 text-white border-violet-600'
//                         : 'bg-background border-border text-foreground hover:bg-muted'
//                     }`}
//                   >
//                     <PenLine className="h-4 w-4" />
//                     Manual — use template as-is
//                   </button>
//                   <button
//                     type="button"
//                     onClick={() => setTplMode('llm')}
//                     className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
//                       tplMode === 'llm'
//                         ? 'bg-violet-600 text-white border-violet-600'
//                         : 'bg-background border-border text-foreground hover:bg-muted'
//                     }`}
//                   >
//                     <Wand2 className="h-4 w-4" />
//                     LLM-Assisted — use as seed
//                   </button>
//                 </div>
//                 <p className="text-xs text-muted-foreground">
//                   {tplMode === 'manual'
//                     ? 'Creates 1 touch per prospect. Variables (name, company, title) are substituted per person. Everything else stays exactly as written.'
//                     : 'Creates 7 personalised AI touches per prospect, using the template\'s structure and offer as a guide.'}
//                 </p>
//               </div>

//               {/* Action buttons */}
//               <div className="flex items-center gap-3 pt-1 flex-wrap">
//                 <Button
//                   disabled={
//                     !tplCampaignId ||
//                     !tplIcpId ||
//                     !tplTemplateId ||
//                     templateSendMut.isPending
//                   }
//                   onClick={() =>
//                     templateSendMut.mutate({
//                       campaignId: tplCampaignId,
//                       icpProfileId: tplIcpId,
//                       templateId: tplTemplateId,
//                       mode: tplMode,
//                       senderName: [profile?.firstName, profile?.lastName].filter(Boolean).join(' '),
//                       senderCompany: profile?.senderCompany ?? '',
//                     })
//                   }
//                 >
//                   {templateSendMut.isPending ? (
//                     <>
//                       <Loader2 className="h-4 w-4 mr-2 animate-spin" />
//                       {tplMode === 'manual' ? 'Rendering for all prospects…' : 'Generating for all prospects…'}
//                     </>
//                   ) : (
//                     <>
//                       {tplMode === 'manual'
//                         ? <PenLine className="h-4 w-4 mr-2" />
//                         : <Wand2 className="h-4 w-4 mr-2" />
//                       }
//                       {tplMode === 'manual' ? 'Render for All Prospects' : 'Generate with Template Seed'}
//                     </>
//                   )}
//                 </Button>

//                 {tplSequences.length > 0 && (
//                   <>
//                     {/* Approve All & Schedule All */}
//                     <Button
//                       variant="default"
//                       className="bg-green-600 hover:bg-green-700 text-white"
//                       disabled={
//                         approvingAll ||
//                         tplSequences.every((s) => s.status === 'Scheduled' || s.status === 'Sent')
//                       }
//                       onClick={handleTplApproveAll}
//                     >
//                       {approvingAll ? (
//                         <>
//                           <Loader2 className="h-4 w-4 mr-2 animate-spin" />
//                           Scheduling…
//                         </>
//                       ) : (
//                         <>
//                           <Clock className="h-4 w-4 mr-2" />
//                           Approve All &amp; Schedule All
//                         </>
//                       )}
//                     </Button>

//                     <Button
//                       variant="ghost"
//                       size="sm"
//                       onClick={() => {
//                         setTplSequences([]);
//                         setTplProspectMap({});
//                         setTplIcpId('');
//                         setTplTemplateId('');
//                         qc.invalidateQueries({ queryKey: ['templates'] });
//                       }}
//                     >
//                       <RefreshCw className="h-3 w-3 mr-1" />
//                       Reset
//                     </Button>
//                   </>
//                 )}
//               </div>

//               {/* Rendered count summary */}
//               {tplSequences.length > 0 && (
//                 <div className="flex items-center gap-3 pt-1 flex-wrap">
//                   <p className="text-xs text-muted-foreground">
//                     <span className="font-semibold text-foreground">{tplSequences.length}</span> email{tplSequences.length !== 1 ? 's' : ''} rendered
//                     {' · '}
//                     <span className="text-green-600 font-medium">
//                       {tplSequences.filter((s) => s.status === 'Scheduled' || s.status === 'Sent').length} scheduled/sent
//                     </span>
//                     {' · '}
//                     <span className="text-muted-foreground">
//                       {tplSequences.filter((s) => s.status === 'Draft').length} pending review
//                     </span>
//                   </p>
//                 </div>
//               )}
//             </CardContent>
//           </Card>

//           {/* Template preview — shown after selection but before render */}
//           {tplTemplateId && tplSequences.length === 0 && !templateSendMut.isPending && (() => {
//             const selectedTpl = templates.find((t) => t.id === tplTemplateId);
//             if (!selectedTpl) return null;
//             return (
//               <Card className="border-dashed border-violet-200">
//                 <CardHeader className="pb-2">
//                   <CardTitle className="text-sm flex items-center gap-2 text-violet-800">
//                     <LayoutTemplate className="h-4 w-4" />
//                     Preview: {selectedTpl.name}
//                   </CardTitle>
//                   <CardDescription className="text-xs capitalize">
//                     {selectedTpl.category?.replace(/_/g, ' ')}
//                   </CardDescription>
//                 </CardHeader>
//                 <CardContent className="space-y-2">
//                   {selectedTpl.subjectTemplate && (
//                     <div>
//                       <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Subject</p>
//                       <p className="text-sm mt-0.5">{selectedTpl.subjectTemplate}</p>
//                     </div>
//                   )}
//                   <div>
//                     <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Body (with raw variables)</p>
//                     <pre className="text-xs mt-0.5 whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed max-h-40 overflow-y-auto">
//                       {selectedTpl.bodyTemplate}
//                     </pre>
//                   </div>
//                 </CardContent>
//               </Card>
//             );
//           })()}

//           {/* Rendered emails — one card per prospect */}
//           {tplSequences.length > 0 && (
//             <div className="space-y-4">
//               <div className="flex items-center justify-between flex-wrap gap-2">
//                 <h4 className="font-medium text-sm">
//                   Rendered Emails
//                   <span className="ml-2 text-xs text-muted-foreground font-normal">
//                     — one per prospect · review individually or use Approve All above
//                   </span>
//                 </h4>
//               </div>

//               <div className="space-y-3">
//                 {tplSequences.map((seq, i) => {
//                   const wc         = wordCount(seq.bodyCopy);
//                   const limit      = WORD_LIMITS[seq.angle] ?? 300;
//                   const over       = wc > limit;
//                   const isSavingT  = savingId === seq.id;
//                   const isSendingT = sendingId === seq.id;

//                   return (
//                     <Card
//                       key={seq.id}
//                       className={
//                         seq.status === 'Scheduled' ? 'border-green-200 bg-green-50/20' :
//                         seq.status === 'Sent'      ? 'border-blue-200 bg-blue-50/20' :
//                         'border-violet-100'
//                       }
//                     >
//                       <CardHeader className="pb-2">
//                         <div className="flex items-start justify-between gap-2 flex-wrap">
//                           <div className="flex items-center gap-2">
//                             {/* Prospect name from the backend prospectMap */}
//                             <div className="h-7 w-7 rounded-full bg-violet-100 flex items-center justify-center text-xs font-bold text-violet-700 shrink-0">
//                               {i + 1}
//                             </div>
//                             <div>
//                               <CardTitle className="text-sm flex items-center gap-2">
//                                 {tplProspectMap[seq.id] || `Prospect ${i + 1}`}
//                                 <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
//                                   Template
//                                 </Badge>
//                               </CardTitle>
//                               <CardDescription className="text-xs">Touch 1 · Day 1</CardDescription>
//                             </div>
//                           </div>
//                           <Badge
//                             variant="outline"
//                             className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
//                           >
//                             {seq.status}
//                           </Badge>
//                         </div>
//                       </CardHeader>

//                       <CardContent className="space-y-3">
//                         <div className="space-y-1">
//                           <Label className="text-xs">Subject</Label>
//                           <Input
//                             value={seq.subjectLine ?? ''}
//                             onChange={(e) => {
//                               const updated = [...tplSequences];
//                               updated[i] = { ...updated[i], subjectLine: e.target.value };
//                               setTplSequences(updated);
//                             }}
//                             className="text-sm"
//                             placeholder="Subject line..."
//                           />
//                         </div>

//                         <div className="space-y-1">
//                           <Label className="text-xs">Body</Label>
//                           <Textarea
//                             value={seq.bodyCopy ?? ''}
//                             onChange={(e) => {
//                               const updated = [...tplSequences];
//                               updated[i] = { ...updated[i], bodyCopy: e.target.value };
//                               setTplSequences(updated);
//                             }}
//                             rows={5}
//                             className="text-sm font-mono"
//                             placeholder="Email body..."
//                           />
//                           <span className={`text-xs ${over ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}>
//                             Words: {wc}{over && ` — over ${limit} limit`}
//                           </span>
//                         </div>

//                         <div className="flex gap-2 flex-wrap">
//                           {/* <TBtn size="sm" variant="outline" tooltip="Save edits"
//                             onClick={() => handleTplSave(seq)} disabled={isSavingT}>
//                             {isSavingT ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Save className="h-3 w-3 mr-1" />}
//                             Save
//                           </TBtn> */}
//                           <TBtn size="sm" variant="outline" tooltip="Approve and queue for Scheduler"
//                             onClick={() => handleTplApprove(seq, i)}
//                             disabled={isSavingT || seq.status === 'Scheduled' || seq.status === 'Sent'}>
//                             <Clock className="h-3 w-3 mr-1" />
//                             {seq.status === 'Scheduled' ? 'Scheduled ✓' : seq.status === 'Sent' ? 'Sent ✓' : 'Approve & Schedule'}
//                           </TBtn>
//                           <TBtn size="sm" variant="ghost" tooltip="Copy body"
//                             onClick={() => { navigator.clipboard.writeText(seq.bodyCopy ?? ''); toast.success('Copied'); }}>
//                             <Copy className="h-3 w-3 mr-1" />Copy
//                           </TBtn>
//                           <TBtn size="sm" variant="ghost" tooltip="Send immediately via MailBridge"
//                             onClick={() => handleTplSendNow(seq, i)}
//                             disabled={isSendingT || seq.status === 'Sent'}>
//                             {isSendingT ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />}
//                             {seq.status === 'Sent' ? 'Sent ✓' : 'Send Now'}
//                           </TBtn>
//                         </div>
//                       </CardContent>
//                     </Card>
//                   );
//                 })}
//               </div>
//             </div>
//           )}

//           {/* Empty state */}
//           {tplSequences.length === 0 && !templateSendMut.isPending && !tplIcpId && (
//             <div className="py-16 text-center text-muted-foreground">
//               <LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-30" />
//               <p className="text-sm">Select a campaign, ICP profile, and template above</p>
//               <p className="text-xs mt-1">
//                 All prospects linked to the selected ICP will get their own rendered email
//               </p>
//             </div>
//           )}

//           {tplSequences.length === 0 && !templateSendMut.isPending && tplIcpId && !tplTemplateId && (
//             <div className="py-10 text-center text-muted-foreground">
//               <p className="text-sm">Now select a template and click Render for All Prospects</p>
//             </div>
//           )}

//         </TabsContent>
//         {/* ── End Tab 2 ───────────────────────────────────────────────────── */}

//       </Tabs>
//     </div>
//   );
// }

import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Layers, Loader2, Copy, FileDown, FileText,
  ChevronDown, ChevronUp, Save, Send, AlertCircle, Clock,
  LayoutTemplate, Wand2, RefreshCw, Bot, PenLine,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { http } from '@/services/apiClient';
import { useAuth } from '@/context/AuthContext';
 
// ─── Types ───────────────────────────────────────────────────────────────────
 
interface Campaign {
  id: string;
  name: string;
  llmConfigId?: string | null;
  icpProfileId?: string | null;
  framework?: string | null;
  senderRole?: string | null;
  senderCompany?: string | null;
  senderOffer?: string | null;
  proofMetric?: string | null;
}
 
interface Prospect {
  id: string;
  firstName: string;
  lastName: string;
  title?: string | null;
  company?: string | null;
  seniority?: string;
  signals?: string | null;
  icpProfileId?: string | null;
}
 
interface Sequence {
  id: string;
  campaignId: string;
  prospectId: string;
  touchNumber: number;
  sendDay: number;
  angle: string;
  framework: string;
  channel: string;
  subjectLine: string | null;
  bodyCopy: string | null;
  qaScore?: number | null;
  status: string;
  personalisationConfidence?: number | null;
  flagForManualReview?: boolean;
  sentAt?: string | null;
}
 
interface EmailTemplateResponse {
  id: string;
  name: string;
  category: string;
  framework: string | null;
  subjectTemplate: string | null;
  bodyTemplate: string;
  variables: string[];
  isShared: boolean;
  createdAt: string;
  updatedAt: string;
}

type TemplateSendMode = 'manual' | 'llm';

// ─── Constants ────────────────────────────────────────────────────────────────
 
const WORD_LIMITS: Record<string, number> = {
  FirstTouch: 150, NewEvidence: 120, DifferentPain: 120,
  IndustryInsight: 120, DirectQuestion: 80, Breakup: 60,
};
 
const TOUCH_INFO = [
  { touch: 1, day: 'Day 1',  angle: 'First Touch',       words: 150, color: 'border-blue-200',    desc: 'The opener. References a specific signal or trigger event. Establishes relevance immediately — no generic intros.' },
  { touch: 2, day: 'Day 3',  angle: 'New Evidence',      words: 120, color: 'border-cyan-200',    desc: 'Follows up with a new data point or case study. Introduces social proof or a metric the prospect cares about.' },
  { touch: 3, day: 'Day 7',  angle: 'Different Pain',    words: 120, color: 'border-teal-200',    desc: 'Pivots to address a different pain point. Each email must work standalone — no "as I mentioned" references.' },
  { touch: 4, day: 'Day 12', angle: 'Industry Insight',  words: 120, color: 'border-emerald-200', desc: 'Shares a relevant industry trend or benchmark. Creates FOMO about what competitors are doing differently.' },
  { touch: 5, day: 'Day 18', angle: 'Direct Question',   words: 80,  color: 'border-amber-200',   desc: 'Short, direct question that demands a response. Example: "Is this still a priority for Q3?" Max 80 words.' },
  { touch: 6, day: 'Day 24', angle: 'Breakup',           words: 60,  color: 'border-rose-200',    desc: 'The "breakup" email. Polite sign-off that creates urgency. Often gets the highest reply rate. Max 60 words.' },
  { touch: 7, day: 'Day 30', angle: 'Breakup (LinkedIn)', words: 60, color: 'border-pink-200',    desc: 'LinkedIn follow-up breakup. Same tone, adapted for the LinkedIn channel.' },
];
 
const STATUS_COLORS: Record<string, string> = {
  Draft:     'bg-muted text-muted-foreground',
  QaPassed:  'bg-emerald-100 text-emerald-700 border-emerald-200',
  Sent:      'bg-blue-100 text-blue-700 border-blue-200',
  Scheduled: 'bg-amber-100 text-amber-700 border-amber-200',
};
 
// ─── Helper ───────────────────────────────────────────────────────────────────
 
function normalise<T>(data: unknown): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  const p = data as { items?: T[] };
  return Array.isArray(p.items) ? p.items : [];
}
 
function parseSignals(signals: string | null | undefined): unknown[] {
  try { return signals ? (JSON.parse(signals) as unknown[]) : []; }
  catch { return []; }
}
 
function wordCount(text: string | null | undefined): number {
  return (text ?? '').split(/\s+/).filter(Boolean).length;
}
 
// ─── Inline Tooltip Button ────────────────────────────────────────────────────
 
function TBtn({
  children, tooltip, disabled, onClick, size = 'sm', variant = 'outline', className = '',
}: {
  children: React.ReactNode; tooltip: string; disabled?: boolean;
  onClick?: () => void; size?: 'sm' | 'default';
  variant?: 'outline' | 'default' | 'ghost'; className?: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button size={size} variant={variant} disabled={disabled} onClick={onClick} className={className}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
}
 
// ─── Component ────────────────────────────────────────────────────────────────
 
export function SequencesPage() {
  // ── Auth / profile ───────────────────────────────────────────────────────
  const { profile } = useAuth();
 
  // ── Server state ────────────────────────────────────────────────────────
  const { data: campaignsRaw, isLoading: cLoading } = useQuery({
    queryKey: ['campaigns', { page: 1, pageSize: 100 }],
    queryFn: () => http.get<unknown>('/api/v1/campaigns', { page: 1, page_size: 100 }),
    staleTime: 30_000,
  });
  const { data: prospectsRaw } = useQuery({
    queryKey: ['prospects', { page: 1, pageSize: 200 }],
    queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
    staleTime: 30_000,
  });
 
  const campaigns = normalise<Campaign>(campaignsRaw);
  const prospects = normalise<Prospect>(prospectsRaw);

  // ── Template list for the Template-Send tab ──────────────────────────────
  const { data: templates = [], isLoading: tplLoading } = useQuery<EmailTemplateResponse[]>({
    queryKey: ['templates'],
    queryFn: () => http.get<EmailTemplateResponse[]>('/api/v1/templates'),
    staleTime: 60_000,
  });

  // ── ICP profile list for the Template-Send tab ───────────────────────────
  const { data: icpProfiles = [], isLoading: icpLoading } = useQuery<{ id: string; name: string }[]>({
    queryKey: ['icp-profiles'],
    queryFn: () => http.get<{ id: string; name: string }[]>('/api/v1/icp-profiles'),
    staleTime: 60_000,
  });

  // ── Template-send mutation ───────────────────────────────────────────────
  const templateSendMut = useMutation({
    mutationFn: (payload: {
      campaignId: string;
      icpProfileId: string;
      templateId: string;
      mode: TemplateSendMode;
      senderName: string;
      senderCompany: string;
      emailSignature: string;
      physicalAddress: string;
    }) =>
      http.post<{ mode: string; templateName: string; sequences: Sequence[]; message: string; prospectMap: Record<string, string> }>(
        '/api/v1/sequences/template-send',
        payload,
      ),
    onSuccess: (data) => {
      setTplSequences(data.sequences);
      setTplProspectMap(data.prospectMap ?? {});
      toast.success(data.message);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? (err instanceof Error ? err.message : 'Template send failed'));
    },
  });
 
  const qc = useQueryClient();

  // ── UI state ────────────────────────────────────────────────────────────
  const [selectedCampaignId, setSelectedCampaignId] = useState('');
  const [selectedProspectId, setSelectedProspectId] = useState('');
  const [framework, setFramework]                   = useState('trigger');
  const [generating, setGenerating]                 = useState(false);
  const [sequences, setSequences]                   = useState<Sequence[]>([]);
  const [savingId, setSavingId]                     = useState<string | null>(null);
  const [sendingId, setSendingId]                   = useState<string | null>(null);
  const [showExplain, setShowExplain]               = useState(false);
  const [exportingCsv, setExportingCsv]             = useState(false);

  // ── Template-Send tab state ──────────────────────────────────────────────
  const [tplCampaignId, setTplCampaignId]           = useState('');
  const [tplIcpId, setTplIcpId]                      = useState('');
  const [tplTemplateId, setTplTemplateId]            = useState('');
  const [tplMode, setTplMode]                        = useState<TemplateSendMode>('manual');
  const [tplSequences, setTplSequences]              = useState<Sequence[]>([]);
  const [tplProspectMap, setTplProspectMap]          = useState<Record<string, string>>({});
  const [approvingAll, setApprovingAll]              = useState(false);
 
  // ── Derived ─────────────────────────────────────────────────────────────
  const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) ?? null;
  const selectedProspect = prospects.find((p) => p.id === selectedProspectId) ?? null;
 
  // ── Handlers ──────────────────────────────────────────────────────────────
 
  const handleGenerate = useCallback(async () => {
    if (!selectedCampaignId || !selectedProspectId) {
      toast.error('Select a campaign and prospect first');
      return;
    }
    setGenerating(true);
    setSequences([]);
    try {
      await http.post('/api/v1/campaigns/campaign-prospects', {
        campaignId:  selectedCampaignId,
        prospectIds: [selectedProspectId],
        action:      'add',
      }).catch(() => {});
 
      await http.post(
        `/api/v1/campaigns/${selectedCampaignId}/generate-sequences`,
        {
          prospectId:    selectedProspectId,
          framework,
          llmConfigId:   selectedCampaign?.llmConfigId ?? null,
          senderRole:    selectedCampaign?.senderRole,
          senderCompany: selectedCampaign?.senderCompany ?? profile?.senderCompany,
          senderOffer:   selectedCampaign?.senderOffer   ?? profile?.senderOffer,
          proofMetric:   selectedCampaign?.proofMetric,
          seniority:     selectedProspect?.seniority,
          signals:       parseSignals(selectedProspect?.signals),
          senderFirstName: profile?.firstName  ?? undefined,
          senderLastName:  profile?.lastName   ?? undefined,
          senderTitle:     profile?.senderTitle ?? undefined,
          senderSignature: profile?.emailSignature ?? undefined,
          unsubscribeUrl:  '{{unsubscribe_url}}',
          physicalAddress: profile?.physicalAddress ?? undefined,
        },
      );
 
      const fetched = await http.get<unknown>(
        '/api/v1/sequences',
        { campaign_id: selectedCampaignId, prospect_id: selectedProspectId, limit: 50 },
      );
      const seqs: Sequence[] = Array.isArray(fetched)
        ? fetched
        : ((fetched as { items?: Sequence[] }).items ?? []);
 
      if (seqs.length === 0) {
        const all = await http.get<unknown>(
          '/api/v1/sequences',
          { campaign_id: selectedCampaignId, limit: 50 },
        );
        const allSeqs: Sequence[] = Array.isArray(all)
          ? all
          : ((all as { items?: Sequence[] }).items ?? []);
        const forProspect = allSeqs.filter((s) => s.prospectId === selectedProspectId);
        setSequences(forProspect);
        toast.success(
          forProspect.length > 0
            ? `${forProspect.length} sequences loaded`
            : 'Sequences generated — check back shortly'
        );
      } else {
        setSequences(seqs);
        toast.success(`${seqs.length}-touch sequence generated`);
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Generation failed');
    } finally { setGenerating(false); }
  }, [selectedCampaignId, selectedProspectId, framework, selectedCampaign, selectedProspect, profile]);
 
  const handleSave = useCallback(async (seq: Sequence) => {
    setSavingId(seq.id);
    try {
      await http.put(`/api/v1/sequences/${seq.id}`, {
        subjectLine: seq.subjectLine,
        bodyCopy:    seq.bodyCopy,
        status:      seq.status === 'Draft' ? 'Draft' : seq.status,
      });
      toast.success(`Touch ${seq.touchNumber} saved`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Save failed');
    } finally { setSavingId(null); }
  }, []);
 
  // FIX: Approve now also calls /scheduled-send so the APScheduler picks up
  // the sequence automatically. Without this, sequences stayed in QaPassed
  // forever and the scheduler (which only queries status=Scheduled) never
  // had anything to send.
  const handleApprove = useCallback(async (seq: Sequence, index: number) => {
    const wc = wordCount(seq.bodyCopy);
    const limit = WORD_LIMITS[seq.angle] ?? 150;
    if (wc > limit) {
      toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit (${wc} words)`);
      return;
    }
    setSavingId(seq.id);
    try {
      await http.put(`/api/v1/sequences/${seq.id}`, {
        subjectLine: seq.subjectLine,
        bodyCopy:    seq.bodyCopy,
        status:      'QaPassed',
      });
      // Move to Scheduled so the APScheduler tick picks it up automatically.
      await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
      const updated = [...sequences];
      updated[index] = { ...updated[index], status: 'Scheduled' };
      setSequences(updated);
      toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Approve failed');
    } finally { setSavingId(null); }
  }, [sequences]);
 
  // FIX: Approve All also schedules every touch in one pass.
  const handleApproveAll = useCallback(async () => {
    for (let i = 0; i < sequences.length; i++) {
      const seq = sequences[i];
      const wc = wordCount(seq.bodyCopy);
      const limit = WORD_LIMITS[seq.angle] ?? 150;
      if (wc > limit) {
        toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit — fix before approving all`);
        return;
      }
    }
    setSavingId('all');
    try {
      // Step 1: set all to QaPassed
      await Promise.all(
        sequences.map((seq) =>
          http.put(`/api/v1/sequences/${seq.id}`, {
            subjectLine: seq.subjectLine,
            bodyCopy:    seq.bodyCopy,
            status:      'QaPassed',
          })
        )
      );
      // Step 2: move all to Scheduled so the APScheduler picks them up.
      await Promise.all(
        sequences.map((seq) =>
          http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {})
        )
      );
      setSequences(sequences.map((s) => ({ ...s, status: 'Scheduled' })));
      toast.success('All touches approved & scheduled');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Approve all failed');
    } finally { setSavingId(null); }
  }, [sequences]);
 
  const handleSendNow = useCallback(async (seq: Sequence, index: number) => {
    setSendingId(seq.id);
    try {
      await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
      const updated = [...sequences];
      updated[index] = { ...updated[index], status: 'Sent' };
      setSequences(updated);
      toast.success(`Touch ${seq.touchNumber} sent`);
    } catch (err: unknown) {
      // Extract FastAPI detail string (warming gate, DNS gate, etc.) if present.
      // AxiosError.message is generic ("Request failed with status 422") — the
      // actual human-readable reason is in error.response.data.detail.
      const detail =
        (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail;
      toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
    } finally { setSendingId(null); }
  }, [sequences]);

  // ── Tab 2 handlers — identical logic but operate on tplSequences ──────────
  // const handleTplSave = useCallback(async (seq: Sequence) => {
  //   setSavingId(seq.id);
  //   try {
  //     await http.put(`/api/v1/sequences/${seq.id}`, {
  //       subjectLine: seq.subjectLine,
  //       bodyCopy:    seq.bodyCopy,
  //       status:      seq.status === 'Draft' ? 'Draft' : seq.status,
  //     });
  //     toast.success(`Touch ${seq.touchNumber} saved`);
  //   } catch (err: unknown) {
  //     toast.error(err instanceof Error ? err.message : 'Save failed');
  //   } finally { setSavingId(null); }
  // }, []);

  // const handleTplApprove = useCallback(async (seq: Sequence, index: number) => {
  //   setSavingId(seq.id);
  //   try {
  //     await http.put(`/api/v1/sequences/${seq.id}`, {
  //       subjectLine: seq.subjectLine,
  //       bodyCopy:    seq.bodyCopy,
  //       status:      'QaPassed',
  //     });
  //     await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
  //     const updated = [...tplSequences];
  //     updated[index] = { ...updated[index], status: 'Scheduled' };
  //     setTplSequences(updated);
  //     toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
  //   } catch (err: unknown) {
  //     toast.error(err instanceof Error ? err.message : 'Approve failed');
  //   } finally { setSavingId(null); }
  // }, [tplSequences]);

  const handleTplSendNow = useCallback(async (seq: Sequence, index: number) => {
    setSendingId(seq.id);
    try {
      await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
      const updated = [...tplSequences];
      updated[index] = { ...updated[index], status: 'Sent' };
      setTplSequences(updated);
      toast.success(`Touch ${seq.touchNumber} sent`);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
    } finally { setSendingId(null); }
  }, [tplSequences]);

  // ── Approve All & Schedule All for Tab 2 ────────────────────────────────
  // Runs sequentially (not Promise.all) to avoid asyncpg prepared-statement
  // cache collisions on the schema-per-tenant search_path switching.
  const handleTplApproveAll = useCallback(async () => {
    const pending = tplSequences.filter((s) => s.status !== 'Scheduled' && s.status !== 'Sent');
    if (pending.length === 0) {
      toast.info('All touches are already scheduled or sent.');
      return;
    }
    setApprovingAll(true);
    let approved = 0;
    const updated = [...tplSequences];
    try {
      for (const seq of pending) {
        await http.put(`/api/v1/sequences/${seq.id}`, {
          subjectLine: seq.subjectLine,
          bodyCopy:    seq.bodyCopy,
          status:      'QaPassed',
        });
        await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
        const idx = updated.findIndex((s) => s.id === seq.id);
        if (idx !== -1) updated[idx] = { ...updated[idx], status: 'Scheduled' };
        approved++;
      }
      setTplSequences([...updated]);
      toast.success(`${approved} email${approved !== 1 ? 's' : ''} approved & scheduled`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? (err instanceof Error ? err.message : 'Approve all failed'));
      setTplSequences([...updated]); // persist partial progress
    } finally { setApprovingAll(false); }
  }, [tplSequences]);

  const handleExportCsv = useCallback(async () => {
    if (!selectedCampaignId) { toast.error('Select a campaign first'); return; }
    setExportingCsv(true);
    try {
      const rows = sequences.length > 0
        ? sequences
        : await http.get<Sequence[]>('/api/v1/sequences/export', {
            campaign_id: selectedCampaignId,
          });
      const data = Array.isArray(rows) ? rows : sequences;
      const headers = ['touchNumber', 'sendDay', 'angle', 'channel', 'subjectLine', 'bodyCopy', 'qaScore', 'status', 'sentAt'];
      const csv = [
        headers.join(','),
        ...data.map((s) =>
          headers.map((h) => {
            const val = String((s as unknown as Record<string, unknown>)[h] ?? '');
            return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
          }).join(',')
        ),
      ].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `sequences-${selectedCampaignId}-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('CSV exported');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Export failed');
    } finally { setExportingCsv(false); }
  }, [sequences, selectedCampaignId, selectedProspectId]);
 
  // ── Render ───────────────────────────────────────────────────────────────
 
  if (cLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
 
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-lg font-semibold">Sequence Builder</h3>
          <p className="text-sm text-muted-foreground">
            Generate 7-touch AI sequences or send a saved template directly
          </p>
        </div>
 
        {/* Profile status indicator — only shown when profile has loaded AND key fields are genuinely null */}
        {profile !== null && (profile?.emailSignature === null) && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
            <AlertCircle className="h-3 w-3 shrink-0" />
            <span>
              Complete your{' '}
              <a href="/profile" className="underline underline-offset-2">
                profile &amp; signature
              </a>{' '}
              for personalised emails
            </span>
          </div>
        )}
 
        <div className="flex gap-2 flex-wrap">
          <TBtn
            variant="outline"
            tooltip="Export sequences to CSV"
            onClick={handleExportCsv}
            disabled={exportingCsv || (!selectedCampaignId && sequences.length === 0)}
          >
            {exportingCsv
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <FileDown className="h-4 w-4 mr-2" />
            }
            Export CSV
          </TBtn>
          <TBtn
            variant="outline"
            tooltip="How the 7-touch cadence works"
            onClick={() => setShowExplain((v) => !v)}
          >
            <FileText className="h-4 w-4 mr-2" />
            How It Works
            {showExplain ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
          </TBtn>
        </div>
      </div>
 
      {/* ── Main Tabs ─────────────────────────────────────────────────────── */}
      <Tabs defaultValue="ai-generate" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="ai-generate" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            AI Generate
          </TabsTrigger>
          <TabsTrigger value="template-send" className="flex items-center gap-2">
            <LayoutTemplate className="h-4 w-4" />
            Manual Template
          </TabsTrigger>
        </TabsList>

        {/* ── Tab 1: AI Generate (existing flow, unchanged) ─────────────── */}
        <TabsContent value="ai-generate" className="space-y-4 mt-0">

      {/* Configuration Card */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
            <div className="space-y-2">
              <Label>Campaign</Label>
              <Select
                value={selectedCampaignId}
                onValueChange={(v) => { setSelectedCampaignId(v); setSequences([]); }}
              >
                <SelectTrigger><SelectValue placeholder="Select campaign..." /></SelectTrigger>
                <SelectContent className="max-h-64">
                  {campaigns.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {campaigns.length === 0 && (
                <p className="text-xs text-amber-600">Create a campaign first</p>
              )}
            </div>
 
            <div className="space-y-2">
              <Label>Prospect</Label>
              <Select value={selectedProspectId} onValueChange={setSelectedProspectId}>
                <SelectTrigger><SelectValue placeholder="Select prospect..." /></SelectTrigger>
                <SelectContent className="max-h-64">
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName} — {p.company || 'No company'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
 
            <div className="space-y-2">
              <Label>Framework</Label>
              <Select value={framework} onValueChange={setFramework}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="trigger">Trigger-Based</SelectItem>
                  <SelectItem value="problem">Problem-First</SelectItem>
                  <SelectItem value="value">Value-First</SelectItem>
                  <SelectItem value="mutual">Mutual Connection</SelectItem>
                  <SelectItem value="direct">Direct Ask</SelectItem>
                </SelectContent>
              </Select>
            </div>
 
            <TBtn
              size="default"
              variant="default"
              tooltip="Generate a 7-touch email sequence"
              onClick={handleGenerate}
              disabled={generating || !selectedCampaignId || !selectedProspectId}
            >
              {generating
                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
                : <><Layers className="h-4 w-4 mr-2" />Generate 7-Touch Sequence</>
              }
            </TBtn>
          </div>
        </CardContent>
      </Card>
 
      {/* Sequence Timeline */}
      {sequences.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm">
              Sequence Timeline
              <span className="ml-2 text-xs text-muted-foreground font-normal">
                ({sequences.filter((s) => s.status === 'Scheduled' || s.status === 'QaPassed').length}/{sequences.length} approved)
              </span>
            </h4>
            {/* Approve All & Schedule — moves every touch to Scheduled in one click */}
            <TBtn
              size="sm"
              variant="outline"
              tooltip="Approve all touches and schedule for automated sending"
              onClick={handleApproveAll}
              disabled={savingId === 'all' || sequences.every((s) => s.status === 'Scheduled' || s.status === 'Sent')}
            >
              {savingId === 'all'
                ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                : <Clock className="h-3 w-3 mr-1" />
              }
              Approve All &amp; Schedule
            </TBtn>
          </div>
 
          <div className="relative">
            {/* Timeline spine */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
 
            {sequences.map((seq, i) => {
              const wc        = wordCount(seq.bodyCopy);
              const limit     = WORD_LIMITS[seq.angle] ?? 150;
              const over      = wc > limit;
              const isSaving  = savingId === seq.id;
              const isSending = sendingId === seq.id;
 
              return (
                <div key={seq.id} className="relative pl-14 pb-6">
                  {/* Touch number bubble */}
                  <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
                    seq.status === 'Scheduled'
                      ? 'bg-amber-500 text-white'
                      : seq.status === 'QaPassed'
                        ? 'bg-emerald-500 text-white'
                        : seq.status === 'Sent'
                          ? 'bg-blue-500 text-white'
                          : 'bg-primary text-primary-foreground'
                  }`}>
                    {seq.touchNumber}
                  </div>
 
                  <Card className={
                    seq.status === 'Scheduled'
                      ? 'border-amber-200'
                      : seq.status === 'QaPassed'
                        ? 'border-emerald-200'
                        : ''
                  }>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div>
                          <CardTitle className="text-sm flex items-center gap-2">
                            Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, ' $1').trim()}
                            {seq.channel === 'LINKEDIN' && (
                              <Badge variant="outline" className="text-[10px] bg-cyan-50 text-cyan-700 border-cyan-200">
                                LinkedIn
                              </Badge>
                            )}
                            {seq.channel === 'EMAIL' && (
                              <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">
                                Email
                              </Badge>
                            )}
                            {seq.qaScore != null && (
                              <Badge
                                variant="outline"
                                className={`text-[10px] ${
                                  seq.qaScore >= 80
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : seq.qaScore >= 60
                                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                                      : 'bg-red-50 text-red-700 border-red-200'
                                }`}
                              >
                                QA {seq.qaScore}/100
                              </Badge>
                            )}
                          </CardTitle>
                          <CardDescription className="text-xs">Send on Day {seq.sendDay}</CardDescription>
                        </div>
                        <Badge
                          variant="outline"
                          className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
                        >
                          {seq.status}
                        </Badge>
                      </div>
 
                      {seq.flagForManualReview && (
                        <div className="flex items-center gap-1 text-xs text-amber-600 mt-1">
                          <AlertCircle className="h-3 w-3 shrink-0" />
                          <span>Low personalisation confidence — review before sending</span>
                        </div>
                      )}
                    </CardHeader>
 
                    <CardContent className="space-y-3">
                      {/* Subject line */}
                      <div className="space-y-1">
                        <Label className="text-xs">Subject</Label>
                        <Input
                          value={seq.subjectLine ?? ''}
                          onChange={(e) => {
                            const updated = [...sequences];
                            updated[i] = { ...updated[i], subjectLine: e.target.value };
                            setSequences(updated);
                          }}
                          className="text-sm"
                          placeholder="Subject line..."
                        />
                      </div>
 
                      {/* Body copy */}
                      <div className="space-y-1">
                        <Label className="text-xs">Body</Label>
                        <Textarea
                          value={seq.bodyCopy ?? ''}
                          onChange={(e) => {
                            const updated = [...sequences];
                            updated[i] = { ...updated[i], bodyCopy: e.target.value };
                            setSequences(updated);
                          }}
                          rows={5}
                          className="text-sm font-mono"
                          placeholder="Email body..."
                        />
                        <div className="flex justify-between text-xs">
                          <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
                            Words: {wc} / {limit}
                            {over && ' — OVER LIMIT'}
                          </span>
                          {seq.personalisationConfidence != null && (
                            <span className="text-muted-foreground">
                              Confidence: {Math.round(seq.personalisationConfidence * 100)}%
                            </span>
                          )}
                        </div>
                      </div>
 
                      {/* Action buttons */}
                      <div className="flex gap-2 flex-wrap">
                        {/* Save */}
                        <TBtn
                          size="sm"
                          variant="outline"
                          tooltip="Save subject and body edits"
                          onClick={() => handleSave(seq)}
                          disabled={isSaving}
                        >
                          {isSaving
                            ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            : <Save className="h-3 w-3 mr-1" />
                          }
                          Save
                        </TBtn>
 
                        {/* Approve & Schedule — replaces the old Approve button */}
                        <TBtn
                          size="sm"
                          variant="outline"
                          tooltip={
                            over
                              ? `Exceeds ${limit}-word limit`
                              : 'Approve and schedule for automated sending'
                          }
                          onClick={() => handleApprove(seq, i)}
                          disabled={isSaving || seq.status === 'Scheduled' || seq.status === 'Sent'}
                        >
                          <Clock className="h-3 w-3 mr-1" />
                          {seq.status === 'Scheduled'
                            ? 'Scheduled'
                            : seq.status === 'Sent'
                              ? 'Sent'
                              : 'Approve & Schedule'
                          }
                        </TBtn>
 
                        {/* Copy body */}
                        <TBtn
                          size="sm"
                          variant="ghost"
                          tooltip="Copy body to clipboard"
                          onClick={() => {
                            navigator.clipboard.writeText(seq.bodyCopy ?? '');
                            toast.success('Copied');
                          }}
                        >
                          <Copy className="h-3 w-3 mr-1" />
                          Copy
                        </TBtn>
 
                        {/* Send Now — manual immediate send, bypasses schedule */}
                        <TBtn
                          size="sm"
                          variant="ghost"
                          tooltip="Send this touch immediately via MailBridge (bypasses schedule)"
                          onClick={() => handleSendNow(seq, i)}
                          disabled={isSending || seq.status === 'Sent'}
                        >
                          {isSending
                            ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            : <Send className="h-3 w-3 mr-1" />
                          }
                          {seq.status === 'Sent' ? 'Sent' : 'Send Now'}
                        </TBtn>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              );
            })}
          </div>
        </div>
      )}
 
      {/* Empty state */}
      {sequences.length === 0 && !generating && (
        <div className="py-16 text-center text-muted-foreground">
          <Layers className="h-12 w-12 mx-auto mb-4 opacity-30" />
          <p className="text-sm">Select a campaign and prospect, then click Generate</p>
          <p className="text-xs mt-1">Creates 7 personalised touches across ~30 days</p>
        </div>
      )}
 
      {/* Cadence Reference Guide */}
      {showExplain && (
        <Card id="seq-explain" className="border-blue-100 bg-blue-50/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4" />
              How the 7-Touch Sequence Works
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              A scientifically-structured cold email cadence designed to maximise reply rates through
              strategic escalation. Each touch uses a different psychological angle sent at an optimised
              interval.
            </p>
 
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {TOUCH_INFO.map((t) => (
                <div key={t.touch} className={`p-3 rounded-lg border ${t.color} space-y-1`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">Touch {t.touch}: {t.angle}</span>
                    <span className="text-xs text-muted-foreground">{t.day}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{t.desc}</p>
                  <p className="text-xs font-medium">{t.words} words max</p>
                </div>
              ))}
            </div>
 
            <div className="bg-muted rounded-lg p-3 text-xs space-y-1">
              <p className="font-medium">Key Principles:</p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li><strong>Standalone Rule:</strong> Each email must make sense if read in isolation</li>
                <li><strong>Escalating Urgency:</strong> Tone gradually increases from helpful to direct</li>
                <li><strong>Peer Test:</strong> Must read like an internal message, not marketing copy</li>
                <li><strong>Word Limits:</strong> Enforced by angle (see cards above) and seniority tier</li>
                <li><strong>No "Checking In":</strong> Banned: "circling back", "just wanted to follow up", "touching base"</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

        </TabsContent>
        {/* ── End Tab 1 ───────────────────────────────────────────────────── */}

        {/* ── Tab 2: Template Send ──────────────────────────────────────── */}
        <TabsContent value="template-send" className="space-y-4 mt-0">

          {/* Explainer */}
          <Card className="border-violet-100 bg-violet-50/40">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <LayoutTemplate className="h-4 w-4 text-violet-600 mt-0.5 shrink-0" />
                <div className="space-y-2 text-xs">
                  <p className="font-medium text-violet-900">How Template Send works</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="flex items-start gap-2">
                      <PenLine className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium text-violet-800">Manual</p>
                        <p className="text-violet-700">
                          Select an ICP profile — the template renders for <strong>every prospect</strong> linked
                          to that ICP. Variables like name, company, and title are substituted per prospect.
                          Signature and unsubscribe footer are injected by MailBridge at send time.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Wand2 className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium text-violet-800">LLM-Assisted</p>
                        <p className="text-violet-700">
                          The AI generates 7 personalised touches per prospect under the ICP,
                          using your template's structure and offer as a guide.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Configuration card */}
          <Card>
            <CardContent className="p-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-start">

                {/* Campaign selector */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-muted-foreground">Campaign</Label>
                  <Select
                    value={tplCampaignId}
                    onValueChange={(v) => { setTplCampaignId(v); setTplSequences([]); }}
                  >
                    <SelectTrigger className="w-full"><SelectValue placeholder="Select campaign..." /></SelectTrigger>
                    <SelectContent className="max-h-64">
                      {campaigns.map((c) => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {campaigns.length === 0 && (
                    <p className="text-xs text-amber-600">Create a campaign first</p>
                  )}
                </div>

                {/* ICP Profile selector */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-muted-foreground">ICP Profile</Label>
                  {icpLoading ? (
                    <div className="h-9 rounded-md border bg-muted animate-pulse" />
                  ) : (
                    <Select
                      value={tplIcpId}
                      onValueChange={(v) => { setTplIcpId(v); setTplSequences([]); }}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select ICP profile..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-64">
                        {icpProfiles.map((icp) => (
                          <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  {icpProfiles.length === 0 && !icpLoading && (
                    <p className="text-xs text-amber-600">
                      No ICP profiles yet —{' '}
                      <a href="/icp" className="underline underline-offset-2">create one</a>
                    </p>
                  )}
                </div>

                {/* Template selector */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-muted-foreground">Template</Label>
                  {tplLoading ? (
                    <div className="h-9 rounded-md border bg-muted animate-pulse" />
                  ) : (
                    <Select value={tplTemplateId} onValueChange={setTplTemplateId}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select template..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-64">
                        {templates.map((t) => (
                          <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  {templates.length === 0 && !tplLoading && (
                    <p className="text-xs text-amber-600">
                      No templates yet —{' '}
                      <a href="/templates" className="underline underline-offset-2">create one</a>
                    </p>
                  )}
                </div>
              </div>

              {/* ICP helper text — below grid so it doesn't affect dropdown alignment */}
              {tplIcpId && (
                <p className="text-xs text-muted-foreground -mt-2">
                  The template will render for all prospects linked to this ICP
                </p>
              )}

              {/* Mode toggle */}
              <div className="space-y-2">
                <Label>Generation mode</Label>
                <div className="flex gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => setTplMode('manual')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
                      tplMode === 'manual'
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'bg-background border-border text-foreground hover:bg-muted'
                    }`}
                  >
                    <PenLine className="h-4 w-4" />
                    Manual — use template as-is
                  </button>
                  <button
                    type="button"
                    onClick={() => setTplMode('llm')}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors ${
                      tplMode === 'llm'
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'bg-background border-border text-foreground hover:bg-muted'
                    }`}
                  >
                    <Wand2 className="h-4 w-4" />
                    LLM-Assisted — use as seed
                  </button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {tplMode === 'manual'
                    ? 'Creates 1 touch per prospect. Variables (name, company, title) are substituted per person. Everything else stays exactly as written.'
                    : 'Creates 7 personalised AI touches per prospect, using the template\'s structure and offer as a guide.'}
                </p>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-3 pt-1 flex-wrap">
                <Button
                  disabled={
                    !tplCampaignId ||
                    !tplIcpId ||
                    !tplTemplateId ||
                    templateSendMut.isPending
                  }
                  onClick={() =>
                    templateSendMut.mutate({
                      campaignId: tplCampaignId,
                      icpProfileId: tplIcpId,
                      templateId: tplTemplateId,
                      mode: tplMode,
                      senderName: [profile?.firstName, profile?.lastName].filter(Boolean).join(' '),
                      senderCompany: profile?.senderCompany ?? '',
                      emailSignature: profile?.emailSignature ?? '',
                      physicalAddress: profile?.physicalAddress ?? '',
                    })
                  }
                >
                  {templateSendMut.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {tplMode === 'manual' ? 'Rendering for all prospects…' : 'Generating for all prospects…'}
                    </>
                  ) : (
                    <>
                      {tplMode === 'manual'
                        ? <PenLine className="h-4 w-4 mr-2" />
                        : <Wand2 className="h-4 w-4 mr-2" />
                      }
                      {tplMode === 'manual' ? 'Render for All Prospects' : 'Generate with Template Seed'}
                    </>
                  )}
                </Button>

                {tplSequences.length > 0 && (
                  <>
                    {/* Approve All & Schedule All */}
                    <Button
                      variant="default"
                      className="bg-green-600 hover:bg-green-700 text-white"
                      disabled={
                        approvingAll ||
                        tplSequences.every((s) => s.status === 'Scheduled' || s.status === 'Sent')
                      }
                      onClick={handleTplApproveAll}
                    >
                      {approvingAll ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Scheduling…
                        </>
                      ) : (
                        <>
                          <Clock className="h-4 w-4 mr-2" />
                          Approve All &amp; Schedule All
                        </>
                      )}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setTplSequences([]);
                        setTplProspectMap({});
                        setTplIcpId('');
                        setTplTemplateId('');
                        qc.invalidateQueries({ queryKey: ['templates'] });
                      }}
                    >
                      <RefreshCw className="h-3 w-3 mr-1" />
                      Reset
                    </Button>
                  </>
                )}
              </div>

              {/* Rendered count summary */}
              {tplSequences.length > 0 && (
                <div className="flex items-center gap-3 pt-1 flex-wrap">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-semibold text-foreground">{tplSequences.length}</span> email{tplSequences.length !== 1 ? 's' : ''} rendered
                    {' · '}
                    <span className="text-green-600 font-medium">
                      {tplSequences.filter((s) => s.status === 'Scheduled' || s.status === 'Sent').length} scheduled/sent
                    </span>
                    {' · '}
                    <span className="text-muted-foreground">
                      {tplSequences.filter((s) => s.status === 'Draft').length} pending review
                    </span>
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Template preview — shown after selection but before render */}
          {tplTemplateId && tplSequences.length === 0 && !templateSendMut.isPending && (() => {
            const selectedTpl = templates.find((t) => t.id === tplTemplateId);
            if (!selectedTpl) return null;
            return (
              <Card className="border-dashed border-violet-200">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2 text-violet-800">
                    <LayoutTemplate className="h-4 w-4" />
                    Preview: {selectedTpl.name}
                  </CardTitle>
                  <CardDescription className="text-xs capitalize">
                    {selectedTpl.category?.replace(/_/g, ' ')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {selectedTpl.subjectTemplate && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Subject</p>
                      <p className="text-sm mt-0.5">{selectedTpl.subjectTemplate}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Body (with raw variables)</p>
                    <pre className="text-xs mt-0.5 whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed max-h-40 overflow-y-auto">
                      {selectedTpl.bodyTemplate}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* Rendered emails — one card per prospect */}
          {tplSequences.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h4 className="font-medium text-sm">
                  Preview
                  <span className="ml-2 text-xs text-muted-foreground font-normal">
                    — showing 1 of {tplSequences.length} rendered email{tplSequences.length !== 1 ? 's' : ''} · use Approve All &amp; Schedule All to send to everyone
                  </span>
                </h4>
              </div>

              {/* Only render the first sequence as a preview card */}
              {(() => {
                const seq = tplSequences[0];
                const i = 0;
                // const isSavingT  = savingId === seq.id;
                const isSendingT = sendingId === seq.id;

                return (
                  <Card
                    className={
                      seq.status === 'Scheduled' ? 'border-green-200 bg-green-50/20' :
                      seq.status === 'Sent'      ? 'border-blue-200 bg-blue-50/20' :
                      'border-violet-100'
                    }
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <div className="h-7 w-7 rounded-full bg-violet-100 flex items-center justify-center text-xs font-bold text-violet-700 shrink-0">
                            1
                          </div>
                          <div>
                            <CardTitle className="text-sm flex items-center gap-2">
                              {tplProspectMap[seq.id] || 'Prospect 1'}
                              <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
                                Preview
                              </Badge>
                            </CardTitle>
                            <CardDescription className="text-xs">Touch 1 · Day 1</CardDescription>
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
                        >
                          {seq.status}
                        </Badge>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Subject</Label>
                        <Input
                          value={seq.subjectLine ?? ''}
                          onChange={(e) => {
                            const updated = [...tplSequences];
                            updated[i] = { ...updated[i], subjectLine: e.target.value };
                            setTplSequences(updated);
                          }}
                          className="text-sm"
                          placeholder="Subject line..."
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Body</Label>
                        <Textarea
                          value={seq.bodyCopy ?? ''}
                          onChange={(e) => {
                            const updated = [...tplSequences];
                            updated[i] = { ...updated[i], bodyCopy: e.target.value };
                            setTplSequences(updated);
                          }}
                          rows={5}
                          className="text-sm font-mono"
                          placeholder="Email body..."
                        />
                      </div>

                      <div className="flex gap-2 flex-wrap">
                        {/* <TBtn size="sm" variant="outline" tooltip="Save edits to this preview"
                          onClick={() => handleTplSave(seq)} disabled={isSavingT}>
                          {isSavingT ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Save className="h-3 w-3 mr-1" />}
                          Save Preview
                        </TBtn> */}
                        <TBtn size="sm" variant="ghost" tooltip="Copy body to clipboard"
                          onClick={() => { navigator.clipboard.writeText(seq.bodyCopy ?? ''); toast.success('Copied'); }}>
                          <Copy className="h-3 w-3 mr-1" />Copy
                        </TBtn>
                        <TBtn size="sm" variant="ghost" tooltip="Send this prospect's email immediately"
                          onClick={() => handleTplSendNow(seq, i)}
                          disabled={isSendingT || seq.status === 'Sent'}>
                          {isSendingT ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />}
                          {seq.status === 'Sent' ? 'Sent ✓' : 'Send Now'}
                        </TBtn>
                      </div>

                      {tplSequences.length > 1 && (
                        <p className="text-xs text-muted-foreground pt-1 border-t border-border">
                          + {tplSequences.length - 1} more prospect{tplSequences.length - 1 !== 1 ? 's' : ''} will receive the same template with their own name and details substituted. Use <strong>Approve All &amp; Schedule All</strong> above to queue all of them.
                        </p>
                      )}
                    </CardContent>
                  </Card>
                );
              })()}
            </div>
          )}

          {/* Empty state */}
          {tplSequences.length === 0 && !templateSendMut.isPending && !tplIcpId && (
            <div className="py-16 text-center text-muted-foreground">
              <LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p className="text-sm">Select a campaign, ICP profile, and template above</p>
              <p className="text-xs mt-1">
                All prospects linked to the selected ICP will get their own rendered email
              </p>
            </div>
          )}

          {tplSequences.length === 0 && !templateSendMut.isPending && tplIcpId && !tplTemplateId && (
            <div className="py-10 text-center text-muted-foreground">
              <p className="text-sm">Now select a template and click Render for All Prospects</p>
            </div>
          )}

        </TabsContent>
        {/* ── End Tab 2 ───────────────────────────────────────────────────── */}

      </Tabs>
    </div>
  );
}