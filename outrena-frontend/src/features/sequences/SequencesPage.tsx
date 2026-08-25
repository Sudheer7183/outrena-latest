

// // // import { useState, useCallback } from 'react';
// // // import { useQuery } from '@tanstack/react-query';
// // // import {
// // //   Layers, Loader2, CheckCircle2, Copy, FileDown, FileText,
// // //   ChevronDown, ChevronUp, Save, Send, AlertCircle,
// // // } from 'lucide-react';
// // // import { Button } from '@/components/ui/button';
// // // import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
// // // import { Input } from '@/components/ui/input';
// // // import { Label } from '@/components/ui/label';
// // // import { Textarea } from '@/components/ui/textarea';
// // // import { Badge } from '@/components/ui/badge';
// // // import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
// // // import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
// // // import { toast } from 'sonner';
// // // import { http } from '@/services/apiClient';
// // // import { useAuth } from '@/context/AuthContext';

// // // // ─── Types ───────────────────────────────────────────────────────────────────

// // // interface Campaign {
// // //   id: string;
// // //   name: string;
// // //   llmConfigId?: string | null;
// // //   icpProfileId?: string | null;
// // //   framework?: string | null;
// // //   senderRole?: string | null;
// // //   senderCompany?: string | null;
// // //   senderOffer?: string | null;
// // //   proofMetric?: string | null;
// // // }

// // // interface Prospect {
// // //   id: string;
// // //   firstName: string;
// // //   lastName: string;
// // //   title?: string | null;
// // //   company?: string | null;
// // //   seniority?: string;
// // //   signals?: string | null;
// // //   icpProfileId?: string | null;
// // // }

// // // interface Sequence {
// // //   id: string;
// // //   campaignId: string;
// // //   prospectId: string;
// // //   touchNumber: number;
// // //   sendDay: number;
// // //   angle: string;
// // //   framework: string;
// // //   channel: string;
// // //   subjectLine: string | null;
// // //   bodyCopy: string | null;
// // //   qaScore?: number | null;
// // //   status: string;
// // //   personalisationConfidence?: number | null;
// // //   flagForManualReview?: boolean;
// // //   sentAt?: string | null;
// // // }

// // // // ─── Constants ────────────────────────────────────────────────────────────────

// // // const WORD_LIMITS: Record<string, number> = {
// // //   FirstTouch: 150, NewEvidence: 120, DifferentPain: 120,
// // //   IndustryInsight: 120, DirectQuestion: 80, Breakup: 60,
// // // };

// // // const TOUCH_INFO = [
// // //   { touch: 1, day: 'Day 1',  angle: 'First Touch',       words: 150, color: 'border-blue-200',    desc: 'The opener. References a specific signal or trigger event. Establishes relevance immediately — no generic intros.' },
// // //   { touch: 2, day: 'Day 3',  angle: 'New Evidence',      words: 120, color: 'border-cyan-200',    desc: 'Follows up with a new data point or case study. Introduces social proof or a metric the prospect cares about.' },
// // //   { touch: 3, day: 'Day 7',  angle: 'Different Pain',    words: 120, color: 'border-teal-200',    desc: 'Pivots to address a different pain point. Each email must work standalone — no "as I mentioned" references.' },
// // //   { touch: 4, day: 'Day 12', angle: 'Industry Insight',  words: 120, color: 'border-emerald-200', desc: 'Shares a relevant industry trend or benchmark. Creates FOMO about what competitors are doing differently.' },
// // //   { touch: 5, day: 'Day 18', angle: 'Direct Question',   words: 80,  color: 'border-amber-200',   desc: 'Short, direct question that demands a response. Example: "Is this still a priority for Q3?" Max 80 words.' },
// // //   { touch: 6, day: 'Day 24', angle: 'Breakup',           words: 60,  color: 'border-rose-200',    desc: 'The "breakup" email. Polite sign-off that creates urgency. Often gets the highest reply rate. Max 60 words.' },
// // //   { touch: 7, day: 'Day 30', angle: 'Breakup (LinkedIn)', words: 60, color: 'border-pink-200',    desc: 'LinkedIn follow-up breakup. Same tone, adapted for the LinkedIn channel.' },
// // // ];

// // // const STATUS_COLORS: Record<string, string> = {
// // //   Draft: 'bg-muted text-muted-foreground',
// // //   QaPassed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
// // //   Sent: 'bg-blue-100 text-blue-700 border-blue-200',
// // //   Scheduled: 'bg-amber-100 text-amber-700 border-amber-200',
// // // };

// // // // ─── Helper ───────────────────────────────────────────────────────────────────

// // // function normalise<T>(data: unknown): T[] {
// // //   if (!data) return [];
// // //   if (Array.isArray(data)) return data as T[];
// // //   const p = data as { items?: T[] };
// // //   return Array.isArray(p.items) ? p.items : [];
// // // }

// // // function parseSignals(signals: string | null | undefined): unknown[] {
// // //   try { return signals ? (JSON.parse(signals) as unknown[]) : []; }
// // //   catch { return []; }
// // // }

// // // function wordCount(text: string | null | undefined): number {
// // //   return (text ?? '').split(/\s+/).filter(Boolean).length;
// // // }

// // // // ─── Inline Tooltip Button ────────────────────────────────────────────────────

// // // function TBtn({
// // //   children, tooltip, disabled, onClick, size = 'sm', variant = 'outline', className = '',
// // // }: {
// // //   children: React.ReactNode; tooltip: string; disabled?: boolean;
// // //   onClick?: () => void; size?: 'sm' | 'default';
// // //   variant?: 'outline' | 'default' | 'ghost'; className?: string;
// // // }) {
// // //   return (
// // //     <Tooltip>
// // //       <TooltipTrigger asChild>
// // //         <Button size={size} variant={variant} disabled={disabled} onClick={onClick} className={className}>
// // //           {children}
// // //         </Button>
// // //       </TooltipTrigger>
// // //       <TooltipContent>{tooltip}</TooltipContent>
// // //     </Tooltip>
// // //   );
// // // }

// // // // ─── Component ────────────────────────────────────────────────────────────────

// // // export function SequencesPage() {
// // //   // ── Auth / profile ───────────────────────────────────────────────────────
// // //   const { profile } = useAuth();

// // //   // ── Server state ────────────────────────────────────────────────────────
// // //   const { data: campaignsRaw, isLoading: cLoading } = useQuery({
// // //     queryKey: ['campaigns', { page: 1, pageSize: 100 }],
// // //     queryFn: () => http.get<unknown>('/api/v1/campaigns', { page: 1, page_size: 100 }),
// // //     staleTime: 30_000,
// // //   });
// // //   const { data: prospectsRaw } = useQuery({
// // //     queryKey: ['prospects', { page: 1, pageSize: 200 }],
// // //     queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
// // //     staleTime: 30_000,
// // //   });

// // //   const campaigns  = normalise<Campaign>(campaignsRaw);
// // //   const prospects  = normalise<Prospect>(prospectsRaw);

// // //   // ── UI state ────────────────────────────────────────────────────────────
// // //   const [selectedCampaignId, setSelectedCampaignId] = useState('');
// // //   const [selectedProspectId, setSelectedProspectId] = useState('');
// // //   const [framework, setFramework]                   = useState('trigger');
// // //   const [generating, setGenerating]                 = useState(false);
// // //   const [sequences, setSequences]                   = useState<Sequence[]>([]);
// // //   const [savingId, setSavingId]                     = useState<string | null>(null);
// // //   const [sendingId, setSendingId]                   = useState<string | null>(null);
// // //   const [showExplain, setShowExplain]               = useState(false);
// // //   const [exportingCsv, setExportingCsv]             = useState(false);

// // //   // ── Derived ─────────────────────────────────────────────────────────────
// // //   const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) ?? null;
// // //   const selectedProspect = prospects.find((p) => p.id === selectedProspectId) ?? null;

// // //   // ── Handlers ─────────────────────────────────────────────────────────────

// // //   const handleGenerate = useCallback(async () => {
// // //     if (!selectedCampaignId || !selectedProspectId) {
// // //       toast.error('Select a campaign and prospect first');
// // //       return;
// // //     }
// // //     setGenerating(true);
// // //     setSequences([]);
// // //     try {
// // //       // Step 1: ensure prospect is linked to campaign (backend requires this)
// // //       await http.post('/api/v1/campaigns/campaign-prospects', {
// // //         campaignId:  selectedCampaignId,
// // //         prospectIds: [selectedProspectId],
// // //         action:      'add',
// // //       }).catch(() => {
// // //         // Ignore — prospect may already be linked
// // //       });

// // //       // Step 2: trigger generation — include sender profile fields so the
// // //       // backend LLM prompt can personalise the signature and sign-off.
// // //       // Fields are optional: if the user has not filled in their profile,
// // //       // the backend falls back gracefully to its existing placeholder text.
// // //       await http.post(
// // //         `/api/v1/campaigns/${selectedCampaignId}/generate-sequences`,
// // //         {
// // //           prospectId:    selectedProspectId,
// // //           framework,
// // //           llmConfigId:   selectedCampaign?.llmConfigId ?? null,
// // //           senderRole:    selectedCampaign?.senderRole,
// // //           senderCompany: selectedCampaign?.senderCompany ?? profile?.senderCompany,
// // //           senderOffer:   selectedCampaign?.senderOffer   ?? profile?.senderOffer,
// // //           proofMetric:   selectedCampaign?.proofMetric,
// // //           seniority:     selectedProspect?.seniority,
// // //           signals:       parseSignals(selectedProspect?.signals),

// // //           // ── Personalisation fields from the logged-in rep's profile ──────
// // //           // These were the missing fields causing [Your Name] placeholders.
// // //           senderFirstName:  profile?.firstName  ?? undefined,
// // //           senderLastName:   profile?.lastName   ?? undefined,
// // //           senderTitle:      profile?.senderTitle ?? undefined,

// // //           // Signature block appended verbatim after the LLM body
// // //           senderSignature:  profile?.emailSignature ?? undefined,

// // //           // CAN-SPAM footer — {{unsubscribe_url}} is replaced by MailBridge
// // //           // at actual send time; physicalAddress satisfies §5(a)(5).
// // //           unsubscribeUrl:   "{{unsubscribe_url}}",
// // //           physicalAddress:  profile?.physicalAddress ?? undefined,
// // //         },
// // //       );

// // //       // Step 3: fetch the sequences from DB (generation stores, doesn't return them)
// // //       // QUERY-PARAM CASING FIX: the backend's GET /api/v1/sequences route
// // //       // declares `campaign_id` / `prospect_id` (snake_case, no alias) —
// // //       // sending camelCase here was silently ignored by FastAPI, so this
// // //       // call was returning ALL sequences (unfiltered) instead of just this
// // //       // prospect's 7 touches. That's why generating for one prospect
// // //       // appeared to show sequences belonging to many other prospects too.
// // //       const fetched = await http.get<unknown>(
// // //         '/api/v1/sequences',
// // //         { campaign_id: selectedCampaignId, prospect_id: selectedProspectId, limit: 50 },
// // //       );
// // //       const seqs: Sequence[] = Array.isArray(fetched)
// // //         ? fetched
// // //         : ((fetched as { items?: Sequence[] }).items ?? []);

// // //       if (seqs.length === 0) {
// // //         // Sequences may already exist — retry with the campaign filter
// // //         // only (still correctly snake_case), then filter to this prospect
// // //         // CLIENT-SIDE ourselves. Previously, if that client-side filter
// // //         // also came back empty, this fell back to showing the ENTIRE
// // //         // campaign's unfiltered sequences — which is exactly how
// // //         // generating for one prospect could appear to show touches
// // //         // belonging to several other prospects. That unsafe fallback is
// // //         // removed: if we truly can't find this prospect's sequences, we
// // //         // show nothing rather than showing someone else's.
// // //         const all = await http.get<unknown>(
// // //           '/api/v1/sequences',
// // //           { campaign_id: selectedCampaignId, limit: 50 },
// // //         );
// // //         const allSeqs: Sequence[] = Array.isArray(all)
// // //           ? all
// // //           : ((all as { items?: Sequence[] }).items ?? []);
// // //         const forProspect = allSeqs.filter((s) => s.prospectId === selectedProspectId);
// // //         setSequences(forProspect);
// // //         toast.success(
// // //           forProspect.length > 0
// // //             ? `${forProspect.length} sequences loaded`
// // //             : 'Sequences generated — check back shortly'
// // //         );
// // //       } else {
// // //         setSequences(seqs);
// // //         toast.success(`${seqs.length}-touch sequence generated`);
// // //       }
// // //     } catch (err: unknown) {
// // //       toast.error(err instanceof Error ? err.message : 'Generation failed');
// // //     } finally { setGenerating(false); }
// // //   }, [selectedCampaignId, selectedProspectId, framework, selectedCampaign, selectedProspect, profile]);

// // //   const handleSave = useCallback(async (seq: Sequence) => {
// // //     setSavingId(seq.id);
// // //     try {
// // //       await http.put(`/api/v1/sequences/${seq.id}`, {
// // //         subjectLine: seq.subjectLine,
// // //         bodyCopy:    seq.bodyCopy,
// // //         status:      seq.status === 'Draft' ? 'Draft' : seq.status,
// // //       });
// // //       toast.success(`Touch ${seq.touchNumber} saved`);
// // //     } catch (err: unknown) {
// // //       toast.error(err instanceof Error ? err.message : 'Save failed');
// // //     } finally { setSavingId(null); }
// // //   }, []);

// // //   const handleApprove = useCallback(async (seq: Sequence, index: number) => {
// // //     const wc = wordCount(seq.bodyCopy);
// // //     const limit = WORD_LIMITS[seq.angle] ?? 150;
// // //     if (wc > limit) {
// // //       toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit (${wc} words)`);
// // //       return;
// // //     }
// // //     setSavingId(seq.id);
// // //     try {
// // //       await http.put(`/api/v1/sequences/${seq.id}`, {
// // //         subjectLine: seq.subjectLine,
// // //         bodyCopy:    seq.bodyCopy,
// // //         status:      'QaPassed',
// // //       });
// // //       const updated = [...sequences];
// // //       updated[index] = { ...updated[index], status: 'QaPassed' };
// // //       setSequences(updated);
// // //       toast.success(`Touch ${seq.touchNumber} approved`);
// // //     } catch (err: unknown) {
// // //       toast.error(err instanceof Error ? err.message : 'Approve failed');
// // //     } finally { setSavingId(null); }
// // //   }, [sequences]);

// // //   const handleApproveAll = useCallback(async () => {
// // //     for (let i = 0; i < sequences.length; i++) {
// // //       const seq = sequences[i];
// // //       const wc = wordCount(seq.bodyCopy);
// // //       const limit = WORD_LIMITS[seq.angle] ?? 150;
// // //       if (wc > limit) {
// // //         toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit — fix before approving all`);
// // //         return;
// // //       }
// // //     }
// // //     setSavingId('all');
// // //     try {
// // //       await Promise.all(
// // //         sequences.map((seq) =>
// // //           http.put(`/api/v1/sequences/${seq.id}`, {
// // //             subjectLine: seq.subjectLine,
// // //             bodyCopy:    seq.bodyCopy,
// // //             status:      'QaPassed',
// // //           })
// // //         )
// // //       );
// // //       setSequences(sequences.map((s) => ({ ...s, status: 'QaPassed' })));
// // //       toast.success('All touches approved');
// // //     } catch (err: unknown) {
// // //       toast.error(err instanceof Error ? err.message : 'Approve all failed');
// // //     } finally { setSavingId(null); }
// // //   }, [sequences]);

// // //   const handleSendNow = useCallback(async (seq: Sequence, index: number) => {
// // //     setSendingId(seq.id);
// // //     // try {
// // //     //   await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
// // //     //   const updated = [...sequences];
// // //     //   updated[index] = { ...updated[index], status: 'Sent' };
// // //     //   setSequences(updated);
// // //     //   toast.success(`Touch ${seq.touchNumber} sent`);
// // //     // } catch (err: unknown) {
// // //     //   toast.error(err instanceof Error ? err.message : 'Send failed');
// // //     // } finally { setSendingId(null); }
// // //     try {
// // //       await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
// // //       const updated = [...sequences];
// // //       updated[index] = { ...updated[index], status: 'Sent' };
// // //       setSequences(updated);
// // //       toast.success(`Touch ${seq.touchNumber} sent`);
// // //     } catch (err: unknown) {
// // //       // Extract FastAPI detail string (warming gate, DNS gate, etc.) if present.
// // //       // AxiosError.message is generic ("Request failed with status 422") — the
// // //       // actual human-readable reason is in error.response.data.detail.
// // //       const detail =
// // //         (err as { response?: { data?: { detail?: string } } })
// // //           ?.response?.data?.detail;
// // //       toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
// // //     } finally { setSendingId(null); }
// // //   }, [sequences]);

// // //   const handleExportCsv = useCallback(async () => {
// // //     if (!selectedCampaignId) { toast.error('Select a campaign first'); return; }
// // //     setExportingCsv(true);
// // //     try {
// // //       const rows = sequences.length > 0
// // //         ? sequences
// // //         // QUERY-PARAM CASING FIX: backend export_sequences only declares
// // //         // `campaign_id` (snake_case, no alias) and doesn't support a
// // //         // prospect filter at all — the fallback path below only ever
// // //         // triggers when `sequences` (already correctly prospect-scoped
// // //         // in memory) is empty, so exporting the whole campaign here is
// // //         // an acceptable fallback rather than a silent scoping bug.
// // //         : await http.get<Sequence[]>('/api/v1/sequences/export', {
// // //             campaign_id: selectedCampaignId,
// // //           });
// // //       const data = Array.isArray(rows) ? rows : sequences;
// // //       const headers = ['touchNumber', 'sendDay', 'angle', 'channel', 'subjectLine', 'bodyCopy', 'qaScore', 'status', 'sentAt'];
// // //       const csv = [
// // //         headers.join(','),
// // //         ...data.map((s) =>
// // //           headers.map((h) => {
// // //             const val = String((s as unknown as Record<string, unknown>)[h] ?? '');
// // //             return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
// // //           }).join(',')
// // //         ),
// // //       ].join('\n');
// // //       const blob = new Blob([csv], { type: 'text/csv' });
// // //       const url  = URL.createObjectURL(blob);
// // //       const a    = document.createElement('a');
// // //       a.href     = url;
// // //       a.download = `sequences-${selectedCampaignId}-${new Date().toISOString().split('T')[0]}.csv`;
// // //       a.click();
// // //       URL.revokeObjectURL(url);
// // //       toast.success('CSV exported');
// // //     } catch (err: unknown) {
// // //       toast.error(err instanceof Error ? err.message : 'Export failed');
// // //     } finally { setExportingCsv(false); }
// // //   }, [sequences, selectedCampaignId, selectedProspectId]);

// // //   // ── Render ───────────────────────────────────────────────────────────────

// // //   if (cLoading) {
// // //     return (
// // //       <div className="flex items-center justify-center h-64">
// // //         <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
// // //       </div>
// // //     );
// // //   }

// // //   return (
// // //     <div className="space-y-6">
// // //       {/* Header */}
// // //       <div className="flex items-center justify-between flex-wrap gap-2">
// // //         <div>
// // //           <h3 className="text-lg font-semibold">Sequence Builder</h3>
// // //           <p className="text-sm text-muted-foreground">
// // //             Generate 7-touch email sequences with escalating cadence
// // //           </p>
// // //         </div>

// // //         {/* Profile status indicator — shown when profile is missing fields */}
// // //         {(!profile?.emailSignature || !profile?.firstName) && (
// // //           <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
// // //             <AlertCircle className="h-3 w-3 shrink-0" />
// // //             <span>
// // //               Complete your{' '}
// // //               <a href="/settings/profile" className="underline underline-offset-2">
// // //                 profile &amp; signature
// // //               </a>{' '}
// // //               for personalised emails
// // //             </span>
// // //           </div>
// // //         )}

// // //         <div className="flex gap-2 flex-wrap">
// // //           <TBtn
// // //             variant="outline"
// // //             tooltip="Export sequences to CSV"
// // //             onClick={handleExportCsv}
// // //             disabled={exportingCsv || (!selectedCampaignId && sequences.length === 0)}
// // //           >
// // //             {exportingCsv
// // //               ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
// // //               : <FileDown className="h-4 w-4 mr-2" />
// // //             }
// // //             Export CSV
// // //           </TBtn>
// // //           <TBtn
// // //             variant="outline"
// // //             tooltip="How the 7-touch cadence works"
// // //             onClick={() => setShowExplain((v) => !v)}
// // //           >
// // //             <FileText className="h-4 w-4 mr-2" />
// // //             How It Works
// // //             {showExplain ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
// // //           </TBtn>
// // //         </div>
// // //       </div>

// // //       {/* Configuration Card */}
// // //       <Card>
// // //         <CardContent className="p-4">
// // //           <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
// // //             <div className="space-y-2">
// // //               <Label>Campaign</Label>
// // //               <Select
// // //                 value={selectedCampaignId}
// // //                 onValueChange={(v) => { setSelectedCampaignId(v); setSequences([]); }}
// // //               >
// // //                 <SelectTrigger><SelectValue placeholder="Select campaign..." /></SelectTrigger>
// // //                 <SelectContent className="max-h-64">
// // //                   {campaigns.map((c) => (
// // //                     <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
// // //                   ))}
// // //                 </SelectContent>
// // //               </Select>
// // //               {campaigns.length === 0 && (
// // //                 <p className="text-xs text-amber-600">Create a campaign first</p>
// // //               )}
// // //             </div>

// // //             <div className="space-y-2">
// // //               <Label>Prospect</Label>
// // //               <Select value={selectedProspectId} onValueChange={setSelectedProspectId}>
// // //                 <SelectTrigger><SelectValue placeholder="Select prospect..." /></SelectTrigger>
// // //                 <SelectContent className="max-h-64">
// // //                   {prospects.map((p) => (
// // //                     <SelectItem key={p.id} value={p.id}>
// // //                       {p.firstName} {p.lastName} — {p.company || 'No company'}
// // //                     </SelectItem>
// // //                   ))}
// // //                 </SelectContent>
// // //               </Select>
// // //             </div>

// // //             <div className="space-y-2">
// // //               <Label>Framework</Label>
// // //               <Select value={framework} onValueChange={setFramework}>
// // //                 <SelectTrigger><SelectValue /></SelectTrigger>
// // //                 <SelectContent>
// // //                   <SelectItem value="trigger">Trigger-Based</SelectItem>
// // //                   <SelectItem value="problem">Problem-First</SelectItem>
// // //                   <SelectItem value="value">Value-First</SelectItem>
// // //                   <SelectItem value="mutual">Mutual Connection</SelectItem>
// // //                   <SelectItem value="direct">Direct Ask</SelectItem>
// // //                 </SelectContent>
// // //               </Select>
// // //             </div>

// // //             <TBtn
// // //               size="default"
// // //               variant="default"
// // //               tooltip="Generate a 7-touch email sequence"
// // //               onClick={handleGenerate}
// // //               disabled={generating || !selectedCampaignId || !selectedProspectId}
// // //             >
// // //               {generating
// // //                 ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
// // //                 : <><Layers className="h-4 w-4 mr-2" />Generate 7-Touch Sequence</>
// // //               }
// // //             </TBtn>
// // //           </div>
// // //         </CardContent>
// // //       </Card>

// // //       {/* Sequence Timeline */}
// // //       {sequences.length > 0 && (
// // //         <div className="space-y-4">
// // //           <div className="flex items-center justify-between">
// // //             <h4 className="font-medium text-sm">
// // //               Sequence Timeline
// // //               <span className="ml-2 text-xs text-muted-foreground font-normal">
// // //                 ({sequences.filter((s) => s.status === 'QaPassed').length}/{sequences.length} approved)
// // //               </span>
// // //             </h4>
// // //             <TBtn
// // //               size="sm"
// // //               variant="outline"
// // //               tooltip="Approve all touches (checks word limits)"
// // //               onClick={handleApproveAll}
// // //               disabled={savingId === 'all'}
// // //             >
// // //               {savingId === 'all'
// // //                 ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// // //                 : <CheckCircle2 className="h-3 w-3 mr-1" />
// // //               }
// // //               Approve All
// // //             </TBtn>
// // //           </div>

// // //           <div className="relative">
// // //             {/* Timeline spine */}
// // //             <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />

// // //             {sequences.map((seq, i) => {
// // //               const wc    = wordCount(seq.bodyCopy);
// // //               const limit = WORD_LIMITS[seq.angle] ?? 150;
// // //               const over  = wc > limit;
// // //               const isSaving  = savingId === seq.id;
// // //               const isSending = sendingId === seq.id;

// // //               return (
// // //                 <div key={seq.id} className="relative pl-14 pb-6">
// // //                   {/* Touch number bubble */}
// // //                   <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
// // //                     seq.status === 'QaPassed'
// // //                       ? 'bg-emerald-500 text-white'
// // //                       : seq.status === 'Sent'
// // //                         ? 'bg-blue-500 text-white'
// // //                         : 'bg-primary text-primary-foreground'
// // //                   }`}>
// // //                     {seq.touchNumber}
// // //                   </div>

// // //                   <Card className={seq.status === 'QaPassed' ? 'border-emerald-200' : ''}>
// // //                     <CardHeader className="pb-2">
// // //                       <div className="flex items-start justify-between gap-2 flex-wrap">
// // //                         <div>
// // //                           <CardTitle className="text-sm flex items-center gap-2">
// // //                             Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, ' $1').trim()}
// // //                             {seq.channel === 'LINKEDIN' && (
// // //                               <Badge variant="outline" className="text-[10px] bg-cyan-50 text-cyan-700 border-cyan-200">
// // //                                 LinkedIn
// // //                               </Badge>
// // //                             )}
// // //                             {seq.channel === 'EMAIL' && (
// // //                               <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">
// // //                                 Email
// // //                               </Badge>
// // //                             )}
// // //                             {/* QA Score badge (SQ-1) */}
// // //                             {seq.qaScore != null && (
// // //                               <Badge
// // //                                 variant="outline"
// // //                                 className={`text-[10px] ${
// // //                                   seq.qaScore >= 80
// // //                                     ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
// // //                                     : seq.qaScore >= 60
// // //                                       ? 'bg-amber-50 text-amber-700 border-amber-200'
// // //                                       : 'bg-red-50 text-red-700 border-red-200'
// // //                                 }`}
// // //                               >
// // //                                 QA {seq.qaScore}/100
// // //                               </Badge>
// // //                             )}
// // //                           </CardTitle>
// // //                           <CardDescription className="text-xs">Send on Day {seq.sendDay}</CardDescription>
// // //                         </div>
// // //                         <Badge
// // //                           variant="outline"
// // //                           className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
// // //                         >
// // //                           {seq.status}
// // //                         </Badge>
// // //                       </div>

// // //                       {/* Personalisation confidence indicator */}
// // //                       {seq.flagForManualReview && (
// // //                         <div className="flex items-center gap-1 text-xs text-amber-600 mt-1">
// // //                           <AlertCircle className="h-3 w-3 shrink-0" />
// // //                           <span>Low personalisation confidence — review before sending</span>
// // //                         </div>
// // //                       )}
// // //                     </CardHeader>

// // //                     <CardContent className="space-y-3">
// // //                       {/* Subject line */}
// // //                       <div className="space-y-1">
// // //                         <Label className="text-xs">Subject</Label>
// // //                         <Input
// // //                           value={seq.subjectLine ?? ''}
// // //                           onChange={(e) => {
// // //                             const updated = [...sequences];
// // //                             updated[i] = { ...updated[i], subjectLine: e.target.value };
// // //                             setSequences(updated);
// // //                           }}
// // //                           className="text-sm"
// // //                           placeholder="Subject line..."
// // //                         />
// // //                       </div>

// // //                       {/* Body copy */}
// // //                       <div className="space-y-1">
// // //                         <Label className="text-xs">Body</Label>
// // //                         <Textarea
// // //                           value={seq.bodyCopy ?? ''}
// // //                           onChange={(e) => {
// // //                             const updated = [...sequences];
// // //                             updated[i] = { ...updated[i], bodyCopy: e.target.value };
// // //                             setSequences(updated);
// // //                           }}
// // //                           rows={5}
// // //                           className="text-sm font-mono"
// // //                           placeholder="Email body..."
// // //                         />
// // //                         {/* Word count */}
// // //                         <div className="flex justify-between text-xs">
// // //                           <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
// // //                             Words: {wc} / {limit}
// // //                             {over && ' — OVER LIMIT'}
// // //                           </span>
// // //                           {seq.personalisationConfidence != null && (
// // //                             <span className="text-muted-foreground">
// // //                               Confidence: {Math.round(seq.personalisationConfidence * 100)}%
// // //                             </span>
// // //                           )}
// // //                         </div>
// // //                       </div>

// // //                       {/* Action buttons */}
// // //                       <div className="flex gap-2 flex-wrap">
// // //                         {/* Save (SQ-2: save on edit, not only on schedule) */}
// // //                         <TBtn
// // //                           size="sm"
// // //                           variant="outline"
// // //                           tooltip="Save subject and body edits"
// // //                           onClick={() => handleSave(seq)}
// // //                           disabled={isSaving}
// // //                         >
// // //                           {isSaving
// // //                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// // //                             : <Save className="h-3 w-3 mr-1" />
// // //                           }
// // //                           Save
// // //                         </TBtn>

// // //                         {/* Approve */}
// // //                         <TBtn
// // //                           size="sm"
// // //                           variant="outline"
// // //                           tooltip={over ? `Exceeds ${limit}-word limit` : 'Approve this touch'}
// // //                           onClick={() => handleApprove(seq, i)}
// // //                           disabled={isSaving || seq.status === 'QaPassed'}
// // //                         >
// // //                           <CheckCircle2 className="h-3 w-3 mr-1" />
// // //                           {seq.status === 'QaPassed' ? 'Approved' : 'Approve'}
// // //                         </TBtn>

// // //                         {/* Copy body (SQ-3) */}
// // //                         <TBtn
// // //                           size="sm"
// // //                           variant="ghost"
// // //                           tooltip="Copy body to clipboard"
// // //                           onClick={() => {
// // //                             navigator.clipboard.writeText(seq.bodyCopy ?? '');
// // //                             toast.success('Copied');
// // //                           }}
// // //                         >
// // //                           <Copy className="h-3 w-3 mr-1" />
// // //                           Copy
// // //                         </TBtn>

// // //                         {/* Send Now */}
// // //                         <TBtn
// // //                           size="sm"
// // //                           variant="ghost"
// // //                           tooltip="Send this touch now via MailBridge"
// // //                           onClick={() => handleSendNow(seq, i)}
// // //                           disabled={isSending || seq.status === 'Sent'}
// // //                         >
// // //                           {isSending
// // //                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// // //                             : <Send className="h-3 w-3 mr-1" />
// // //                           }
// // //                           {seq.status === 'Sent' ? 'Sent' : 'Send Now'}
// // //                         </TBtn>
// // //                       </div>
// // //                     </CardContent>
// // //                   </Card>
// // //                 </div>
// // //               );
// // //             })}
// // //           </div>
// // //         </div>
// // //       )}

// // //       {/* Empty state */}
// // //       {sequences.length === 0 && !generating && (
// // //         <div className="py-16 text-center text-muted-foreground">
// // //           <Layers className="h-12 w-12 mx-auto mb-4 opacity-30" />
// // //           <p className="text-sm">Select a campaign and prospect, then click Generate</p>
// // //           <p className="text-xs mt-1">Creates 7 personalised touches across ~30 days</p>
// // //         </div>
// // //       )}

// // //       {/* Cadence Reference Guide (SQ-4) */}
// // //       {showExplain && (
// // //         <Card id="seq-explain" className="border-blue-100 bg-blue-50/30">
// // //           <CardHeader className="pb-3">
// // //             <CardTitle className="text-sm flex items-center gap-2">
// // //               <FileText className="h-4 w-4" />
// // //               How the 7-Touch Sequence Works
// // //             </CardTitle>
// // //           </CardHeader>
// // //           <CardContent className="space-y-4 text-sm">
// // //             <p className="text-muted-foreground">
// // //               A scientifically-structured cold email cadence designed to maximise reply rates through
// // //               strategic escalation. Each touch uses a different psychological angle sent at an optimised
// // //               interval.
// // //             </p>

// // //             <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
// // //               {TOUCH_INFO.map((t) => (
// // //                 <div key={t.touch} className={`p-3 rounded-lg border ${t.color} space-y-1`}>
// // //                   <div className="flex items-center justify-between">
// // //                     <span className="font-medium text-sm">Touch {t.touch}: {t.angle}</span>
// // //                     <span className="text-xs text-muted-foreground">{t.day}</span>
// // //                   </div>
// // //                   <p className="text-xs text-muted-foreground">{t.desc}</p>
// // //                   <p className="text-xs font-medium">{t.words} words max</p>
// // //                 </div>
// // //               ))}
// // //             </div>

// // //             <div className="bg-muted rounded-lg p-3 text-xs space-y-1">
// // //               <p className="font-medium">Key Principles:</p>
// // //               <ul className="list-disc list-inside space-y-1 text-muted-foreground">
// // //                 <li><strong>Standalone Rule:</strong> Each email must make sense if read in isolation</li>
// // //                 <li><strong>Escalating Urgency:</strong> Tone gradually increases from helpful to direct</li>
// // //                 <li><strong>Peer Test:</strong> Must read like an internal message, not marketing copy</li>
// // //                 <li><strong>Word Limits:</strong> Enforced by angle (see cards above) and seniority tier</li>
// // //                 <li><strong>No "Checking In":</strong> Banned: "circling back", "just wanted to follow up", "touching base"</li>
// // //               </ul>
// // //             </div>
// // //           </CardContent>
// // //         </Card>
// // //       )}
// // //     </div>
// // //   );
// // // }

// // import { useState, useCallback } from 'react';
// // import { useQuery } from '@tanstack/react-query';
// // import {
// //   Layers, Loader2, Copy, FileDown, FileText,
// //   ChevronDown, ChevronUp, Save, Send, AlertCircle, Clock,
// // } from 'lucide-react';
// // import { Button } from '@/components/ui/button';
// // import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
// // import { Input } from '@/components/ui/input';
// // import { Label } from '@/components/ui/label';
// // import { Textarea } from '@/components/ui/textarea';
// // import { Badge } from '@/components/ui/badge';
// // import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
// // import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
// // import { toast } from 'sonner';
// // import { http } from '@/services/apiClient';
// // import { useAuth } from '@/context/AuthContext';
 
// // // ─── Types ───────────────────────────────────────────────────────────────────
 
// // interface Campaign {
// //   id: string;
// //   name: string;
// //   llmConfigId?: string | null;
// //   icpProfileId?: string | null;
// //   framework?: string | null;
// //   senderRole?: string | null;
// //   senderCompany?: string | null;
// //   senderOffer?: string | null;
// //   proofMetric?: string | null;
// // }
 
// // interface Prospect {
// //   id: string;
// //   firstName: string;
// //   lastName: string;
// //   title?: string | null;
// //   company?: string | null;
// //   seniority?: string;
// //   signals?: string | null;
// //   icpProfileId?: string | null;
// // }
 
// // interface Sequence {
// //   id: string;
// //   campaignId: string;
// //   prospectId: string;
// //   touchNumber: number;
// //   sendDay: number;
// //   angle: string;
// //   framework: string;
// //   channel: string;
// //   subjectLine: string | null;
// //   bodyCopy: string | null;
// //   qaScore?: number | null;
// //   status: string;
// //   personalisationConfidence?: number | null;
// //   flagForManualReview?: boolean;
// //   sentAt?: string | null;
// // }
 
// // // ─── Constants ────────────────────────────────────────────────────────────────
 
// // const WORD_LIMITS: Record<string, number> = {
// //   FirstTouch: 150, NewEvidence: 120, DifferentPain: 120,
// //   IndustryInsight: 120, DirectQuestion: 80, Breakup: 60,
// // };
 
// // const TOUCH_INFO = [
// //   { touch: 1, day: 'Day 1',  angle: 'First Touch',       words: 150, color: 'border-blue-200',    desc: 'The opener. References a specific signal or trigger event. Establishes relevance immediately — no generic intros.' },
// //   { touch: 2, day: 'Day 3',  angle: 'New Evidence',      words: 120, color: 'border-cyan-200',    desc: 'Follows up with a new data point or case study. Introduces social proof or a metric the prospect cares about.' },
// //   { touch: 3, day: 'Day 7',  angle: 'Different Pain',    words: 120, color: 'border-teal-200',    desc: 'Pivots to address a different pain point. Each email must work standalone — no "as I mentioned" references.' },
// //   { touch: 4, day: 'Day 12', angle: 'Industry Insight',  words: 120, color: 'border-emerald-200', desc: 'Shares a relevant industry trend or benchmark. Creates FOMO about what competitors are doing differently.' },
// //   { touch: 5, day: 'Day 18', angle: 'Direct Question',   words: 80,  color: 'border-amber-200',   desc: 'Short, direct question that demands a response. Example: "Is this still a priority for Q3?" Max 80 words.' },
// //   { touch: 6, day: 'Day 24', angle: 'Breakup',           words: 60,  color: 'border-rose-200',    desc: 'The "breakup" email. Polite sign-off that creates urgency. Often gets the highest reply rate. Max 60 words.' },
// //   { touch: 7, day: 'Day 30', angle: 'Breakup (LinkedIn)', words: 60, color: 'border-pink-200',    desc: 'LinkedIn follow-up breakup. Same tone, adapted for the LinkedIn channel.' },
// // ];
 
// // const STATUS_COLORS: Record<string, string> = {
// //   Draft:     'bg-muted text-muted-foreground',
// //   QaPassed:  'bg-emerald-100 text-emerald-700 border-emerald-200',
// //   Sent:      'bg-blue-100 text-blue-700 border-blue-200',
// //   Scheduled: 'bg-amber-100 text-amber-700 border-amber-200',
// // };
 
// // // ─── Helper ───────────────────────────────────────────────────────────────────
 
// // function normalise<T>(data: unknown): T[] {
// //   if (!data) return [];
// //   if (Array.isArray(data)) return data as T[];
// //   const p = data as { items?: T[] };
// //   return Array.isArray(p.items) ? p.items : [];
// // }
 
// // function parseSignals(signals: string | null | undefined): unknown[] {
// //   try { return signals ? (JSON.parse(signals) as unknown[]) : []; }
// //   catch { return []; }
// // }
 
// // function wordCount(text: string | null | undefined): number {
// //   return (text ?? '').split(/\s+/).filter(Boolean).length;
// // }
 
// // // ─── Inline Tooltip Button ────────────────────────────────────────────────────
 
// // function TBtn({
// //   children, tooltip, disabled, onClick, size = 'sm', variant = 'outline', className = '',
// // }: {
// //   children: React.ReactNode; tooltip: string; disabled?: boolean;
// //   onClick?: () => void; size?: 'sm' | 'default';
// //   variant?: 'outline' | 'default' | 'ghost'; className?: string;
// // }) {
// //   return (
// //     <Tooltip>
// //       <TooltipTrigger asChild>
// //         <Button size={size} variant={variant} disabled={disabled} onClick={onClick} className={className}>
// //           {children}
// //         </Button>
// //       </TooltipTrigger>
// //       <TooltipContent>{tooltip}</TooltipContent>
// //     </Tooltip>
// //   );
// // }
 
// // // ─── Component ────────────────────────────────────────────────────────────────
 
// // export function SequencesPage() {
// //   // ── Auth / profile ───────────────────────────────────────────────────────
// //   const { profile } = useAuth();
 
// //   // ── Server state ────────────────────────────────────────────────────────
// //   const { data: campaignsRaw, isLoading: cLoading } = useQuery({
// //     queryKey: ['campaigns', { page: 1, pageSize: 100 }],
// //     queryFn: () => http.get<unknown>('/api/v1/campaigns', { page: 1, page_size: 100 }),
// //     staleTime: 30_000,
// //   });
// //   const { data: prospectsRaw } = useQuery({
// //     queryKey: ['prospects', { page: 1, pageSize: 200 }],
// //     queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
// //     staleTime: 30_000,
// //   });
 
// //   const campaigns = normalise<Campaign>(campaignsRaw);
// //   const prospects = normalise<Prospect>(prospectsRaw);
 
// //   // ── UI state ────────────────────────────────────────────────────────────
// //   const [selectedCampaignId, setSelectedCampaignId] = useState('');
// //   const [selectedProspectId, setSelectedProspectId] = useState('');
// //   const [framework, setFramework]                   = useState('trigger');
// //   const [generating, setGenerating]                 = useState(false);
// //   const [sequences, setSequences]                   = useState<Sequence[]>([]);
// //   const [savingId, setSavingId]                     = useState<string | null>(null);
// //   const [sendingId, setSendingId]                   = useState<string | null>(null);
// //   const [showExplain, setShowExplain]               = useState(false);
// //   const [exportingCsv, setExportingCsv]             = useState(false);
 
// //   // ── Derived ─────────────────────────────────────────────────────────────
// //   const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) ?? null;
// //   const selectedProspect = prospects.find((p) => p.id === selectedProspectId) ?? null;
 
// //   // ── Handlers ──────────────────────────────────────────────────────────────
 
// //   const handleGenerate = useCallback(async () => {
// //     if (!selectedCampaignId || !selectedProspectId) {
// //       toast.error('Select a campaign and prospect first');
// //       return;
// //     }
// //     setGenerating(true);
// //     setSequences([]);
// //     try {
// //       await http.post('/api/v1/campaigns/campaign-prospects', {
// //         campaignId:  selectedCampaignId,
// //         prospectIds: [selectedProspectId],
// //         action:      'add',
// //       }).catch(() => {});
 
// //       await http.post(
// //         `/api/v1/campaigns/${selectedCampaignId}/generate-sequences`,
// //         {
// //           prospectId:    selectedProspectId,
// //           framework,
// //           llmConfigId:   selectedCampaign?.llmConfigId ?? null,
// //           senderRole:    selectedCampaign?.senderRole,
// //           senderCompany: selectedCampaign?.senderCompany ?? profile?.senderCompany,
// //           senderOffer:   selectedCampaign?.senderOffer   ?? profile?.senderOffer,
// //           proofMetric:   selectedCampaign?.proofMetric,
// //           seniority:     selectedProspect?.seniority,
// //           signals:       parseSignals(selectedProspect?.signals),
// //           senderFirstName: profile?.firstName  ?? undefined,
// //           senderLastName:  profile?.lastName   ?? undefined,
// //           senderTitle:     profile?.senderTitle ?? undefined,
// //           senderSignature: profile?.emailSignature ?? undefined,
// //           unsubscribeUrl:  '{{unsubscribe_url}}',
// //           physicalAddress: profile?.physicalAddress ?? undefined,
// //         },
// //       );
 
// //       const fetched = await http.get<unknown>(
// //         '/api/v1/sequences',
// //         { campaign_id: selectedCampaignId, prospect_id: selectedProspectId, limit: 50 },
// //       );
// //       const seqs: Sequence[] = Array.isArray(fetched)
// //         ? fetched
// //         : ((fetched as { items?: Sequence[] }).items ?? []);
 
// //       if (seqs.length === 0) {
// //         const all = await http.get<unknown>(
// //           '/api/v1/sequences',
// //           { campaign_id: selectedCampaignId, limit: 50 },
// //         );
// //         const allSeqs: Sequence[] = Array.isArray(all)
// //           ? all
// //           : ((all as { items?: Sequence[] }).items ?? []);
// //         const forProspect = allSeqs.filter((s) => s.prospectId === selectedProspectId);
// //         setSequences(forProspect);
// //         toast.success(
// //           forProspect.length > 0
// //             ? `${forProspect.length} sequences loaded`
// //             : 'Sequences generated — check back shortly'
// //         );
// //       } else {
// //         setSequences(seqs);
// //         toast.success(`${seqs.length}-touch sequence generated`);
// //       }
// //     } catch (err: unknown) {
// //       toast.error(err instanceof Error ? err.message : 'Generation failed');
// //     } finally { setGenerating(false); }
// //   }, [selectedCampaignId, selectedProspectId, framework, selectedCampaign, selectedProspect, profile]);
 
// //   const handleSave = useCallback(async (seq: Sequence) => {
// //     setSavingId(seq.id);
// //     try {
// //       await http.put(`/api/v1/sequences/${seq.id}`, {
// //         subjectLine: seq.subjectLine,
// //         bodyCopy:    seq.bodyCopy,
// //         status:      seq.status === 'Draft' ? 'Draft' : seq.status,
// //       });
// //       toast.success(`Touch ${seq.touchNumber} saved`);
// //     } catch (err: unknown) {
// //       toast.error(err instanceof Error ? err.message : 'Save failed');
// //     } finally { setSavingId(null); }
// //   }, []);
 
// //   // FIX: Approve now also calls /scheduled-send so the APScheduler picks up
// //   // the sequence automatically. Without this, sequences stayed in QaPassed
// //   // forever and the scheduler (which only queries status=Scheduled) never
// //   // had anything to send.
// //   const handleApprove = useCallback(async (seq: Sequence, index: number) => {
// //     const wc = wordCount(seq.bodyCopy);
// //     const limit = WORD_LIMITS[seq.angle] ?? 150;
// //     if (wc > limit) {
// //       toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit (${wc} words)`);
// //       return;
// //     }
// //     setSavingId(seq.id);
// //     try {
// //       await http.put(`/api/v1/sequences/${seq.id}`, {
// //         subjectLine: seq.subjectLine,
// //         bodyCopy:    seq.bodyCopy,
// //         status:      'QaPassed',
// //       });
// //       // Move to Scheduled so the APScheduler tick picks it up automatically.
// //       await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
// //       const updated = [...sequences];
// //       updated[index] = { ...updated[index], status: 'Scheduled' };
// //       setSequences(updated);
// //       toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
// //     } catch (err: unknown) {
// //       toast.error(err instanceof Error ? err.message : 'Approve failed');
// //     } finally { setSavingId(null); }
// //   }, [sequences]);
 
// //   // FIX: Approve All also schedules every touch in one pass.
// //   const handleApproveAll = useCallback(async () => {
// //     for (let i = 0; i < sequences.length; i++) {
// //       const seq = sequences[i];
// //       const wc = wordCount(seq.bodyCopy);
// //       const limit = WORD_LIMITS[seq.angle] ?? 150;
// //       if (wc > limit) {
// //         toast.error(`Touch ${seq.touchNumber} exceeds ${limit}-word limit — fix before approving all`);
// //         return;
// //       }
// //     }
// //     setSavingId('all');
// //     try {
// //       // Step 1: set all to QaPassed
// //       await Promise.all(
// //         sequences.map((seq) =>
// //           http.put(`/api/v1/sequences/${seq.id}`, {
// //             subjectLine: seq.subjectLine,
// //             bodyCopy:    seq.bodyCopy,
// //             status:      'QaPassed',
// //           })
// //         )
// //       );
// //       // Step 2: move all to Scheduled so the APScheduler picks them up.
// //       await Promise.all(
// //         sequences.map((seq) =>
// //           http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {})
// //         )
// //       );
// //       setSequences(sequences.map((s) => ({ ...s, status: 'Scheduled' })));
// //       toast.success('All touches approved & scheduled');
// //     } catch (err: unknown) {
// //       toast.error(err instanceof Error ? err.message : 'Approve all failed');
// //     } finally { setSavingId(null); }
// //   }, [sequences]);
 
// //   const handleSendNow = useCallback(async (seq: Sequence, index: number) => {
// //     setSendingId(seq.id);
// //     try {
// //       await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
// //       const updated = [...sequences];
// //       updated[index] = { ...updated[index], status: 'Sent' };
// //       setSequences(updated);
// //       toast.success(`Touch ${seq.touchNumber} sent`);
// //     } catch (err: unknown) {
// //       // Extract FastAPI detail string (warming gate, DNS gate, etc.) if present.
// //       // AxiosError.message is generic ("Request failed with status 422") — the
// //       // actual human-readable reason is in error.response.data.detail.
// //       const detail =
// //         (err as { response?: { data?: { detail?: string } } })
// //           ?.response?.data?.detail;
// //       toast.error(detail ?? (err instanceof Error ? err.message : 'Send failed'));
// //     } finally { setSendingId(null); }
// //   }, [sequences]);
 
// //   const handleExportCsv = useCallback(async () => {
// //     if (!selectedCampaignId) { toast.error('Select a campaign first'); return; }
// //     setExportingCsv(true);
// //     try {
// //       const rows = sequences.length > 0
// //         ? sequences
// //         : await http.get<Sequence[]>('/api/v1/sequences/export', {
// //             campaign_id: selectedCampaignId,
// //           });
// //       const data = Array.isArray(rows) ? rows : sequences;
// //       const headers = ['touchNumber', 'sendDay', 'angle', 'channel', 'subjectLine', 'bodyCopy', 'qaScore', 'status', 'sentAt'];
// //       const csv = [
// //         headers.join(','),
// //         ...data.map((s) =>
// //           headers.map((h) => {
// //             const val = String((s as unknown as Record<string, unknown>)[h] ?? '');
// //             return val.includes(',') ? `"${val.replace(/"/g, '""')}"` : val;
// //           }).join(',')
// //         ),
// //       ].join('\n');
// //       const blob = new Blob([csv], { type: 'text/csv' });
// //       const url  = URL.createObjectURL(blob);
// //       const a    = document.createElement('a');
// //       a.href     = url;
// //       a.download = `sequences-${selectedCampaignId}-${new Date().toISOString().split('T')[0]}.csv`;
// //       a.click();
// //       URL.revokeObjectURL(url);
// //       toast.success('CSV exported');
// //     } catch (err: unknown) {
// //       toast.error(err instanceof Error ? err.message : 'Export failed');
// //     } finally { setExportingCsv(false); }
// //   }, [sequences, selectedCampaignId, selectedProspectId]);
 
// //   // ── Render ───────────────────────────────────────────────────────────────
 
// //   if (cLoading) {
// //     return (
// //       <div className="flex items-center justify-center h-64">
// //         <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
// //       </div>
// //     );
// //   }
 
// //   return (
// //     <div className="space-y-6">
// //       {/* Header */}
// //       <div className="flex items-center justify-between flex-wrap gap-2">
// //         <div>
// //           <h3 className="text-lg font-semibold">Sequence Builder</h3>
// //           <p className="text-sm text-muted-foreground">
// //             Generate 7-touch email sequences with escalating cadence
// //           </p>
// //         </div>
 
// //         {/* Profile status indicator — shown when profile is missing fields */}
// //         {(!profile?.emailSignature || !profile?.firstName) && (
// //           <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
// //             <AlertCircle className="h-3 w-3 shrink-0" />
// //             <span>
// //               Complete your{' '}
// //               <a href="/settings/profile" className="underline underline-offset-2">
// //                 profile &amp; signature
// //               </a>{' '}
// //               for personalised emails
// //             </span>
// //           </div>
// //         )}
 
// //         <div className="flex gap-2 flex-wrap">
// //           <TBtn
// //             variant="outline"
// //             tooltip="Export sequences to CSV"
// //             onClick={handleExportCsv}
// //             disabled={exportingCsv || (!selectedCampaignId && sequences.length === 0)}
// //           >
// //             {exportingCsv
// //               ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
// //               : <FileDown className="h-4 w-4 mr-2" />
// //             }
// //             Export CSV
// //           </TBtn>
// //           <TBtn
// //             variant="outline"
// //             tooltip="How the 7-touch cadence works"
// //             onClick={() => setShowExplain((v) => !v)}
// //           >
// //             <FileText className="h-4 w-4 mr-2" />
// //             How It Works
// //             {showExplain ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
// //           </TBtn>
// //         </div>
// //       </div>
 
// //       {/* Configuration Card */}
// //       <Card>
// //         <CardContent className="p-4">
// //           <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
// //             <div className="space-y-2">
// //               <Label>Campaign</Label>
// //               <Select
// //                 value={selectedCampaignId}
// //                 onValueChange={(v) => { setSelectedCampaignId(v); setSequences([]); }}
// //               >
// //                 <SelectTrigger><SelectValue placeholder="Select campaign..." /></SelectTrigger>
// //                 <SelectContent className="max-h-64">
// //                   {campaigns.map((c) => (
// //                     <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
// //                   ))}
// //                 </SelectContent>
// //               </Select>
// //               {campaigns.length === 0 && (
// //                 <p className="text-xs text-amber-600">Create a campaign first</p>
// //               )}
// //             </div>
 
// //             <div className="space-y-2">
// //               <Label>Prospect</Label>
// //               <Select value={selectedProspectId} onValueChange={setSelectedProspectId}>
// //                 <SelectTrigger><SelectValue placeholder="Select prospect..." /></SelectTrigger>
// //                 <SelectContent className="max-h-64">
// //                   {prospects.map((p) => (
// //                     <SelectItem key={p.id} value={p.id}>
// //                       {p.firstName} {p.lastName} — {p.company || 'No company'}
// //                     </SelectItem>
// //                   ))}
// //                 </SelectContent>
// //               </Select>
// //             </div>
 
// //             <div className="space-y-2">
// //               <Label>Framework</Label>
// //               <Select value={framework} onValueChange={setFramework}>
// //                 <SelectTrigger><SelectValue /></SelectTrigger>
// //                 <SelectContent>
// //                   <SelectItem value="trigger">Trigger-Based</SelectItem>
// //                   <SelectItem value="problem">Problem-First</SelectItem>
// //                   <SelectItem value="value">Value-First</SelectItem>
// //                   <SelectItem value="mutual">Mutual Connection</SelectItem>
// //                   <SelectItem value="direct">Direct Ask</SelectItem>
// //                 </SelectContent>
// //               </Select>
// //             </div>
 
// //             <TBtn
// //               size="default"
// //               variant="default"
// //               tooltip="Generate a 7-touch email sequence"
// //               onClick={handleGenerate}
// //               disabled={generating || !selectedCampaignId || !selectedProspectId}
// //             >
// //               {generating
// //                 ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
// //                 : <><Layers className="h-4 w-4 mr-2" />Generate 7-Touch Sequence</>
// //               }
// //             </TBtn>
// //           </div>
// //         </CardContent>
// //       </Card>
 
// //       {/* Sequence Timeline */}
// //       {sequences.length > 0 && (
// //         <div className="space-y-4">
// //           <div className="flex items-center justify-between">
// //             <h4 className="font-medium text-sm">
// //               Sequence Timeline
// //               <span className="ml-2 text-xs text-muted-foreground font-normal">
// //                 ({sequences.filter((s) => s.status === 'Scheduled' || s.status === 'QaPassed').length}/{sequences.length} approved)
// //               </span>
// //             </h4>
// //             {/* Approve All & Schedule — moves every touch to Scheduled in one click */}
// //             <TBtn
// //               size="sm"
// //               variant="outline"
// //               tooltip="Approve all touches and schedule for automated sending"
// //               onClick={handleApproveAll}
// //               disabled={savingId === 'all' || sequences.every((s) => s.status === 'Scheduled' || s.status === 'Sent')}
// //             >
// //               {savingId === 'all'
// //                 ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// //                 : <Clock className="h-3 w-3 mr-1" />
// //               }
// //               Approve All &amp; Schedule
// //             </TBtn>
// //           </div>
 
// //           <div className="relative">
// //             {/* Timeline spine */}
// //             <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
 
// //             {sequences.map((seq, i) => {
// //               const wc        = wordCount(seq.bodyCopy);
// //               const limit     = WORD_LIMITS[seq.angle] ?? 150;
// //               const over      = wc > limit;
// //               const isSaving  = savingId === seq.id;
// //               const isSending = sendingId === seq.id;
 
// //               return (
// //                 <div key={seq.id} className="relative pl-14 pb-6">
// //                   {/* Touch number bubble */}
// //                   <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
// //                     seq.status === 'Scheduled'
// //                       ? 'bg-amber-500 text-white'
// //                       : seq.status === 'QaPassed'
// //                         ? 'bg-emerald-500 text-white'
// //                         : seq.status === 'Sent'
// //                           ? 'bg-blue-500 text-white'
// //                           : 'bg-primary text-primary-foreground'
// //                   }`}>
// //                     {seq.touchNumber}
// //                   </div>
 
// //                   <Card className={
// //                     seq.status === 'Scheduled'
// //                       ? 'border-amber-200'
// //                       : seq.status === 'QaPassed'
// //                         ? 'border-emerald-200'
// //                         : ''
// //                   }>
// //                     <CardHeader className="pb-2">
// //                       <div className="flex items-start justify-between gap-2 flex-wrap">
// //                         <div>
// //                           <CardTitle className="text-sm flex items-center gap-2">
// //                             Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, ' $1').trim()}
// //                             {seq.channel === 'LINKEDIN' && (
// //                               <Badge variant="outline" className="text-[10px] bg-cyan-50 text-cyan-700 border-cyan-200">
// //                                 LinkedIn
// //                               </Badge>
// //                             )}
// //                             {seq.channel === 'EMAIL' && (
// //                               <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">
// //                                 Email
// //                               </Badge>
// //                             )}
// //                             {seq.qaScore != null && (
// //                               <Badge
// //                                 variant="outline"
// //                                 className={`text-[10px] ${
// //                                   seq.qaScore >= 80
// //                                     ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
// //                                     : seq.qaScore >= 60
// //                                       ? 'bg-amber-50 text-amber-700 border-amber-200'
// //                                       : 'bg-red-50 text-red-700 border-red-200'
// //                                 }`}
// //                               >
// //                                 QA {seq.qaScore}/100
// //                               </Badge>
// //                             )}
// //                           </CardTitle>
// //                           <CardDescription className="text-xs">Send on Day {seq.sendDay}</CardDescription>
// //                         </div>
// //                         <Badge
// //                           variant="outline"
// //                           className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
// //                         >
// //                           {seq.status}
// //                         </Badge>
// //                       </div>
 
// //                       {seq.flagForManualReview && (
// //                         <div className="flex items-center gap-1 text-xs text-amber-600 mt-1">
// //                           <AlertCircle className="h-3 w-3 shrink-0" />
// //                           <span>Low personalisation confidence — review before sending</span>
// //                         </div>
// //                       )}
// //                     </CardHeader>
 
// //                     <CardContent className="space-y-3">
// //                       {/* Subject line */}
// //                       <div className="space-y-1">
// //                         <Label className="text-xs">Subject</Label>
// //                         <Input
// //                           value={seq.subjectLine ?? ''}
// //                           onChange={(e) => {
// //                             const updated = [...sequences];
// //                             updated[i] = { ...updated[i], subjectLine: e.target.value };
// //                             setSequences(updated);
// //                           }}
// //                           className="text-sm"
// //                           placeholder="Subject line..."
// //                         />
// //                       </div>
 
// //                       {/* Body copy */}
// //                       <div className="space-y-1">
// //                         <Label className="text-xs">Body</Label>
// //                         <Textarea
// //                           value={seq.bodyCopy ?? ''}
// //                           onChange={(e) => {
// //                             const updated = [...sequences];
// //                             updated[i] = { ...updated[i], bodyCopy: e.target.value };
// //                             setSequences(updated);
// //                           }}
// //                           rows={5}
// //                           className="text-sm font-mono"
// //                           placeholder="Email body..."
// //                         />
// //                         <div className="flex justify-between text-xs">
// //                           <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
// //                             Words: {wc} / {limit}
// //                             {over && ' — OVER LIMIT'}
// //                           </span>
// //                           {seq.personalisationConfidence != null && (
// //                             <span className="text-muted-foreground">
// //                               Confidence: {Math.round(seq.personalisationConfidence * 100)}%
// //                             </span>
// //                           )}
// //                         </div>
// //                       </div>
 
// //                       {/* Action buttons */}
// //                       <div className="flex gap-2 flex-wrap">
// //                         {/* Save */}
// //                         <TBtn
// //                           size="sm"
// //                           variant="outline"
// //                           tooltip="Save subject and body edits"
// //                           onClick={() => handleSave(seq)}
// //                           disabled={isSaving}
// //                         >
// //                           {isSaving
// //                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// //                             : <Save className="h-3 w-3 mr-1" />
// //                           }
// //                           Save
// //                         </TBtn>
 
// //                         {/* Approve & Schedule — replaces the old Approve button */}
// //                         <TBtn
// //                           size="sm"
// //                           variant="outline"
// //                           tooltip={
// //                             over
// //                               ? `Exceeds ${limit}-word limit`
// //                               : 'Approve and schedule for automated sending'
// //                           }
// //                           onClick={() => handleApprove(seq, i)}
// //                           disabled={isSaving || seq.status === 'Scheduled' || seq.status === 'Sent'}
// //                         >
// //                           <Clock className="h-3 w-3 mr-1" />
// //                           {seq.status === 'Scheduled'
// //                             ? 'Scheduled'
// //                             : seq.status === 'Sent'
// //                               ? 'Sent'
// //                               : 'Approve & Schedule'
// //                           }
// //                         </TBtn>
 
// //                         {/* Copy body */}
// //                         <TBtn
// //                           size="sm"
// //                           variant="ghost"
// //                           tooltip="Copy body to clipboard"
// //                           onClick={() => {
// //                             navigator.clipboard.writeText(seq.bodyCopy ?? '');
// //                             toast.success('Copied');
// //                           }}
// //                         >
// //                           <Copy className="h-3 w-3 mr-1" />
// //                           Copy
// //                         </TBtn>
 
// //                         {/* Send Now — manual immediate send, bypasses schedule */}
// //                         <TBtn
// //                           size="sm"
// //                           variant="ghost"
// //                           tooltip="Send this touch immediately via MailBridge (bypasses schedule)"
// //                           onClick={() => handleSendNow(seq, i)}
// //                           disabled={isSending || seq.status === 'Sent'}
// //                         >
// //                           {isSending
// //                             ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
// //                             : <Send className="h-3 w-3 mr-1" />
// //                           }
// //                           {seq.status === 'Sent' ? 'Sent' : 'Send Now'}
// //                         </TBtn>
// //                       </div>
// //                     </CardContent>
// //                   </Card>
// //                 </div>
// //               );
// //             })}
// //           </div>
// //         </div>
// //       )}
 
// //       {/* Empty state */}
// //       {sequences.length === 0 && !generating && (
// //         <div className="py-16 text-center text-muted-foreground">
// //           <Layers className="h-12 w-12 mx-auto mb-4 opacity-30" />
// //           <p className="text-sm">Select a campaign and prospect, then click Generate</p>
// //           <p className="text-xs mt-1">Creates 7 personalised touches across ~30 days</p>
// //         </div>
// //       )}
 
// //       {/* Cadence Reference Guide */}
// //       {showExplain && (
// //         <Card id="seq-explain" className="border-blue-100 bg-blue-50/30">
// //           <CardHeader className="pb-3">
// //             <CardTitle className="text-sm flex items-center gap-2">
// //               <FileText className="h-4 w-4" />
// //               How the 7-Touch Sequence Works
// //             </CardTitle>
// //           </CardHeader>
// //           <CardContent className="space-y-4 text-sm">
// //             <p className="text-muted-foreground">
// //               A scientifically-structured cold email cadence designed to maximise reply rates through
// //               strategic escalation. Each touch uses a different psychological angle sent at an optimised
// //               interval.
// //             </p>
 
// //             <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
// //               {TOUCH_INFO.map((t) => (
// //                 <div key={t.touch} className={`p-3 rounded-lg border ${t.color} space-y-1`}>
// //                   <div className="flex items-center justify-between">
// //                     <span className="font-medium text-sm">Touch {t.touch}: {t.angle}</span>
// //                     <span className="text-xs text-muted-foreground">{t.day}</span>
// //                   </div>
// //                   <p className="text-xs text-muted-foreground">{t.desc}</p>
// //                   <p className="text-xs font-medium">{t.words} words max</p>
// //                 </div>
// //               ))}
// //             </div>
 
// //             <div className="bg-muted rounded-lg p-3 text-xs space-y-1">
// //               <p className="font-medium">Key Principles:</p>
// //               <ul className="list-disc list-inside space-y-1 text-muted-foreground">
// //                 <li><strong>Standalone Rule:</strong> Each email must make sense if read in isolation</li>
// //                 <li><strong>Escalating Urgency:</strong> Tone gradually increases from helpful to direct</li>
// //                 <li><strong>Peer Test:</strong> Must read like an internal message, not marketing copy</li>
// //                 <li><strong>Word Limits:</strong> Enforced by angle (see cards above) and seniority tier</li>
// //                 <li><strong>No "Checking In":</strong> Banned: "circling back", "just wanted to follow up", "touching base"</li>
// //               </ul>
// //             </div>
// //           </CardContent>
// //         </Card>
// //       )}
// //     </div>
// //   );
// // }

// import { useState, useCallback } from 'react';
// import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
// import {
//   Layers, Loader2, Copy, FileDown, FileText,
//   ChevronDown, ChevronUp, Save, Send, AlertCircle, Clock,
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

//   // ── Template-send mutation ───────────────────────────────────────────────
//   const templateSendMut = useMutation({
//     mutationFn: (payload: {
//       campaignId: string;
//       prospectId: string;
//       templateId: string;
//       mode: TemplateSendMode;
//     }) =>
//       http.post<{ mode: string; templateName: string; sequences: Sequence[]; message: string }>(
//         '/api/v1/sequences/template-send',
//         payload,
//       ),
//     onSuccess: (data) => {
//       setTplSequences(data.sequences);
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
//   // These are separate from the AI Generate tab — they don't interfere with
//   // each other's campaign/prospect selections.
//   const [tplCampaignId, setTplCampaignId]           = useState('');
//   const [tplProspectId, setTplProspectId]            = useState('');
//   const [tplTemplateId, setTplTemplateId]            = useState('');
//   const [tplMode, setTplMode]                        = useState<TemplateSendMode>('manual');
//   const [tplSequences, setTplSequences]              = useState<Sequence[]>([]);
 
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
 
//   const handleSave = useCallback(async (seq: Sequence) => {
//     setSavingId(seq.id);
//     try {
//       await http.put(`/api/v1/sequences/${seq.id}`, {
//         subjectLine: seq.subjectLine,
//         bodyCopy:    seq.bodyCopy,
//         status:      seq.status === 'Draft' ? 'Draft' : seq.status,
//       });
//       toast.success(`Touch ${seq.touchNumber} saved`);
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Save failed');
//     } finally { setSavingId(null); }
//   }, []);
 
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
//   const handleTplSave = useCallback(async (seq: Sequence) => {
//     setSavingId(seq.id);
//     try {
//       await http.put(`/api/v1/sequences/${seq.id}`, {
//         subjectLine: seq.subjectLine,
//         bodyCopy:    seq.bodyCopy,
//         status:      seq.status === 'Draft' ? 'Draft' : seq.status,
//       });
//       toast.success(`Touch ${seq.touchNumber} saved`);
//     } catch (err: unknown) {
//       toast.error(err instanceof Error ? err.message : 'Save failed');
//     } finally { setSavingId(null); }
//   }, []);

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
//             Template Send
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
//                         <TBtn
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
//                         </TBtn>
 
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
//                           Uses your saved template exactly as written — only the prospect's name,
//                           company, and title are substituted in. No LLM call. One touch is created
//                           for review. Signature and unsubscribe footer are added by MailBridge at
//                           send time.
//                         </p>
//                       </div>
//                     </div>
//                     <div className="flex items-start gap-2">
//                       <Wand2 className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
//                       <div>
//                         <p className="font-medium text-violet-800">LLM-Assisted</p>
//                         <p className="text-violet-700">
//                           Your template body is passed to the AI as a structural seed — the AI
//                           writes all 7 personalised touches using the template's tone, structure,
//                           and offer as a guide. Requires a configured LLM on the campaign.
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
//               <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-end">
//                 {/* Campaign selector */}
//                 <div className="space-y-2">
//                   <Label>Campaign</Label>
//                   <Select
//                     value={tplCampaignId}
//                     onValueChange={(v) => { setTplCampaignId(v); setTplSequences([]); }}
//                   >
//                     <SelectTrigger><SelectValue placeholder="Select campaign..." /></SelectTrigger>
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

//                 {/* Prospect selector */}
//                 <div className="space-y-2">
//                   <Label>Prospect</Label>
//                   <Select value={tplProspectId} onValueChange={setTplProspectId}>
//                     <SelectTrigger><SelectValue placeholder="Select prospect..." /></SelectTrigger>
//                     <SelectContent className="max-h-64">
//                       {prospects.map((p) => (
//                         <SelectItem key={p.id} value={p.id}>
//                           {p.firstName} {p.lastName} — {p.company || 'No company'}
//                         </SelectItem>
//                       ))}
//                     </SelectContent>
//                   </Select>
//                 </div>

//                 {/* Template selector */}
//                 <div className="space-y-2">
//                   <Label>Template</Label>
//                   {tplLoading ? (
//                     <div className="h-9 rounded-md border bg-muted animate-pulse" />
//                   ) : (
//                     <Select value={tplTemplateId} onValueChange={setTplTemplateId}>
//                       <SelectTrigger>
//                         <SelectValue placeholder="Select template..." />
//                       </SelectTrigger>
//                       <SelectContent className="max-h-64">
//                         {templates.map((t) => (
//                           <SelectItem key={t.id} value={t.id}>
//                             {t.name}
//                           </SelectItem>
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

//               {/* Mode toggle */}
//               <div className="space-y-2">
//                 <Label>Generation mode</Label>
//                 <div className="flex gap-2">
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
//                     ? 'Creates 1 touch. Only {{first_name}}, {{company}}, {{title}}, {{last_name}} are substituted. Everything else is used exactly as written.'
//                     : 'Creates 7 touches. The AI uses your template\'s structure and tone as guidance while personalising each email for this prospect.'}
//                 </p>
//               </div>

//               {/* Action button */}
//               <div className="flex items-center gap-3 pt-1">
//                 <Button
//                   disabled={
//                     !tplCampaignId ||
//                     !tplProspectId ||
//                     !tplTemplateId ||
//                     templateSendMut.isPending
//                   }
//                   onClick={() =>
//                     templateSendMut.mutate({
//                       campaignId: tplCampaignId,
//                       prospectId: tplProspectId,
//                       templateId: tplTemplateId,
//                       mode: tplMode,
//                     })
//                   }
//                 >
//                   {templateSendMut.isPending ? (
//                     <>
//                       <Loader2 className="h-4 w-4 mr-2 animate-spin" />
//                       {tplMode === 'manual' ? 'Rendering…' : 'Generating…'}
//                     </>
//                   ) : (
//                     <>
//                       {tplMode === 'manual' ? (
//                         <PenLine className="h-4 w-4 mr-2" />
//                       ) : (
//                         <Wand2 className="h-4 w-4 mr-2" />
//                       )}
//                       {tplMode === 'manual' ? 'Render Template' : 'Generate with Template Seed'}
//                     </>
//                   )}
//                 </Button>
//                 {tplSequences.length > 0 && (
//                   <Button
//                     variant="ghost"
//                     size="sm"
//                     onClick={() => { setTplSequences([]); qc.invalidateQueries({ queryKey: ['templates'] }); }}
//                   >
//                     <RefreshCw className="h-3 w-3 mr-1" />
//                     Reset
//                   </Button>
//                 )}
//               </div>
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
//                     {selectedTpl.category.replace(/_/g, ' ')}
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
//                     <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Body</p>
//                     <pre className="text-xs mt-0.5 whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed max-h-40 overflow-y-auto">
//                       {selectedTpl.bodyTemplate}
//                     </pre>
//                   </div>
//                 </CardContent>
//               </Card>
//             );
//           })()}

//           {/* Rendered sequence timeline — same cards as AI Generate tab */}
//           {tplSequences.length > 0 && (
//             <div className="space-y-4">
//               <div className="flex items-center justify-between">
//                 <h4 className="font-medium text-sm">
//                   {tplMode === 'manual' ? 'Rendered Touch' : 'Generated Sequence'}
//                   <span className="ml-2 text-xs text-muted-foreground font-normal">
//                     ({tplSequences.length} {tplSequences.length === 1 ? 'touch' : 'touches'} — review and send)
//                   </span>
//                 </h4>
//               </div>

//               <div className="relative">
//                 <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />

//                 {tplSequences.map((seq, i) => {
//                   const wc        = wordCount(seq.bodyCopy);
//                   const limit     = WORD_LIMITS[seq.angle] ?? 300;
//                   const over      = wc > limit;
//                   const isSavingT = savingId === seq.id;
//                   const isSendingT = sendingId === seq.id;

//                   return (
//                     <div key={seq.id} className="relative pl-14 pb-6">
//                       <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
//                         seq.status === 'Scheduled'
//                           ? 'bg-amber-500 text-white'
//                           : seq.status === 'Sent'
//                             ? 'bg-blue-500 text-white'
//                             : 'bg-violet-500 text-white'
//                       }`}>
//                         {seq.touchNumber}
//                       </div>

//                       <Card className={seq.status === 'Scheduled' ? 'border-amber-200' : 'border-violet-100'}>
//                         <CardHeader className="pb-2">
//                           <div className="flex items-start justify-between gap-2 flex-wrap">
//                             <div>
//                               <CardTitle className="text-sm flex items-center gap-2">
//                                 Touch {seq.touchNumber}
//                                 {tplMode === 'manual' && (
//                                   <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
//                                     Template
//                                   </Badge>
//                                 )}
//                               </CardTitle>
//                               <CardDescription className="text-xs">Send on Day {seq.sendDay}</CardDescription>
//                             </div>
//                             <Badge
//                               variant="outline"
//                               className={`text-xs ${STATUS_COLORS[seq.status] ?? 'bg-muted text-muted-foreground'}`}
//                             >
//                               {seq.status}
//                             </Badge>
//                           </div>
//                         </CardHeader>

//                         <CardContent className="space-y-3">
//                           <div className="space-y-1">
//                             <Label className="text-xs">Subject</Label>
//                             <Input
//                               value={seq.subjectLine ?? ''}
//                               onChange={(e) => {
//                                 const updated = [...tplSequences];
//                                 updated[i] = { ...updated[i], subjectLine: e.target.value };
//                                 setTplSequences(updated);
//                               }}
//                               className="text-sm"
//                               placeholder="Subject line..."
//                             />
//                           </div>

//                           <div className="space-y-1">
//                             <Label className="text-xs">Body</Label>
//                             <Textarea
//                               value={seq.bodyCopy ?? ''}
//                               onChange={(e) => {
//                                 const updated = [...tplSequences];
//                                 updated[i] = { ...updated[i], bodyCopy: e.target.value };
//                                 setTplSequences(updated);
//                               }}
//                               rows={6}
//                               className="text-sm font-mono"
//                               placeholder="Email body..."
//                             />
//                             <div className="flex justify-between text-xs">
//                               <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
//                                 Words: {wc}{over && ` — over ${limit} limit`}
//                               </span>
//                             </div>
//                           </div>

//                           <div className="flex gap-2 flex-wrap">
//                             <TBtn
//                               size="sm"
//                               variant="outline"
//                               tooltip="Save edits to this touch"
//                               onClick={() => handleTplSave(seq)}
//                               disabled={isSavingT}
//                             >
//                               {isSavingT
//                                 ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
//                                 : <Save className="h-3 w-3 mr-1" />
//                               }
//                               Save
//                             </TBtn>

//                             <TBtn
//                               size="sm"
//                               variant="outline"
//                               tooltip="Approve and schedule for automated sending"
//                               onClick={() => handleTplApprove(seq, i)}
//                               disabled={isSavingT || seq.status === 'Scheduled' || seq.status === 'Sent'}
//                             >
//                               <Clock className="h-3 w-3 mr-1" />
//                               {seq.status === 'Scheduled' ? 'Scheduled' : seq.status === 'Sent' ? 'Sent' : 'Approve & Schedule'}
//                             </TBtn>

//                             <TBtn
//                               size="sm"
//                               variant="ghost"
//                               tooltip="Copy body to clipboard"
//                               onClick={() => {
//                                 navigator.clipboard.writeText(seq.bodyCopy ?? '');
//                                 toast.success('Copied');
//                               }}
//                             >
//                               <Copy className="h-3 w-3 mr-1" />
//                               Copy
//                             </TBtn>

//                             <TBtn
//                               size="sm"
//                               variant="ghost"
//                               tooltip="Send immediately via MailBridge"
//                               onClick={() => handleTplSendNow(seq, i)}
//                               disabled={isSendingT || seq.status === 'Sent'}
//                             >
//                               {isSendingT
//                                 ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
//                                 : <Send className="h-3 w-3 mr-1" />
//                               }
//                               {seq.status === 'Sent' ? 'Sent' : 'Send Now'}
//                             </TBtn>
//                           </div>
//                         </CardContent>
//                       </Card>
//                     </div>
//                   );
//                 })}
//               </div>
//             </div>
//           )}

//           {/* Empty state */}
//           {tplSequences.length === 0 && !templateSendMut.isPending && !tplTemplateId && (
//             <div className="py-16 text-center text-muted-foreground">
//               <LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-30" />
//               <p className="text-sm">Select a campaign, prospect, and template above</p>
//               <p className="text-xs mt-1">
//                 Choose Manual to send the template as-is, or LLM-Assisted to use it as a creative seed
//               </p>
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

  // ── Template-send mutation ───────────────────────────────────────────────
  const templateSendMut = useMutation({
    mutationFn: (payload: {
      campaignId: string;
      prospectId: string;
      templateId: string;
      mode: TemplateSendMode;
      senderName: string;
      senderCompany: string;
    }) =>
      http.post<{ mode: string; templateName: string; sequences: Sequence[]; message: string }>(
        '/api/v1/sequences/template-send',
        payload,
      ),
    onSuccess: (data) => {
      setTplSequences(data.sequences);
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
  // These are separate from the AI Generate tab — they don't interfere with
  // each other's campaign/prospect selections.
  const [tplCampaignId, setTplCampaignId]           = useState('');
  const [tplProspectId, setTplProspectId]            = useState('');
  const [tplTemplateId, setTplTemplateId]            = useState('');
  const [tplMode, setTplMode]                        = useState<TemplateSendMode>('manual');
  const [tplSequences, setTplSequences]              = useState<Sequence[]>([]);
 
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
  const handleTplSave = useCallback(async (seq: Sequence) => {
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

  const handleTplApprove = useCallback(async (seq: Sequence, index: number) => {
    setSavingId(seq.id);
    try {
      await http.put(`/api/v1/sequences/${seq.id}`, {
        subjectLine: seq.subjectLine,
        bodyCopy:    seq.bodyCopy,
        status:      'QaPassed',
      });
      await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, {});
      const updated = [...tplSequences];
      updated[index] = { ...updated[index], status: 'Scheduled' };
      setTplSequences(updated);
      toast.success(`Touch ${seq.touchNumber} approved & scheduled`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Approve failed');
    } finally { setSavingId(null); }
  }, [tplSequences]);

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
 
        {/* Profile status indicator — shown when profile is missing fields */}
        {(!profile?.emailSignature || !profile?.firstName) && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
            <AlertCircle className="h-3 w-3 shrink-0" />
            <span>
              Complete your{' '}
              <a href="/settings/profile" className="underline underline-offset-2">
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
                          Uses your saved template exactly as written — only the prospect's name,
                          company, and title are substituted in. No LLM call. One touch is created
                          for review. Signature and unsubscribe footer are added by MailBridge at
                          send time.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Wand2 className="h-3.5 w-3.5 text-violet-600 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium text-violet-800">LLM-Assisted</p>
                        <p className="text-violet-700">
                          Your template body is passed to the AI as a structural seed — the AI
                          writes all 7 personalised touches using the template's tone, structure,
                          and offer as a guide. Requires a configured LLM on the campaign.
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-end">
                {/* Campaign selector */}
                <div className="space-y-2">
                  <Label>Campaign</Label>
                  <Select
                    value={tplCampaignId}
                    onValueChange={(v) => { setTplCampaignId(v); setTplSequences([]); }}
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

                {/* Prospect selector */}
                <div className="space-y-2">
                  <Label>Prospect</Label>
                  <Select value={tplProspectId} onValueChange={setTplProspectId}>
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

                {/* Template selector */}
                <div className="space-y-2">
                  <Label>Template</Label>
                  {tplLoading ? (
                    <div className="h-9 rounded-md border bg-muted animate-pulse" />
                  ) : (
                    <Select value={tplTemplateId} onValueChange={setTplTemplateId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select template..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-64">
                        {templates.map((t) => (
                          <SelectItem key={t.id} value={t.id}>
                            {t.name}
                          </SelectItem>
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

              {/* Mode toggle */}
              <div className="space-y-2">
                <Label>Generation mode</Label>
                <div className="flex gap-2">
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
                    ? 'Creates 1 touch. Only {{first_name}}, {{company}}, {{title}}, {{last_name}} are substituted. Everything else is used exactly as written.'
                    : 'Creates 7 touches. The AI uses your template\'s structure and tone as guidance while personalising each email for this prospect.'}
                </p>
              </div>

              {/* Action button */}
              <div className="flex items-center gap-3 pt-1">
                <Button
                  disabled={
                    !tplCampaignId ||
                    !tplProspectId ||
                    !tplTemplateId ||
                    templateSendMut.isPending
                  }
                  onClick={() =>
                    templateSendMut.mutate({
                      campaignId: tplCampaignId,
                      prospectId: tplProspectId,
                      templateId: tplTemplateId,
                      mode: tplMode,
                      senderName: [profile?.firstName, profile?.lastName].filter(Boolean).join(' '),
                      senderCompany: profile?.senderCompany ?? '',
                    })
                  }
                >
                  {templateSendMut.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {tplMode === 'manual' ? 'Rendering…' : 'Generating…'}
                    </>
                  ) : (
                    <>
                      {tplMode === 'manual' ? (
                        <PenLine className="h-4 w-4 mr-2" />
                      ) : (
                        <Wand2 className="h-4 w-4 mr-2" />
                      )}
                      {tplMode === 'manual' ? 'Render Template' : 'Generate with Template Seed'}
                    </>
                  )}
                </Button>
                {tplSequences.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setTplSequences([]); qc.invalidateQueries({ queryKey: ['templates'] }); }}
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Reset
                  </Button>
                )}
              </div>
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
                    {selectedTpl.category.replace(/_/g, ' ')}
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
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Body</p>
                    <pre className="text-xs mt-0.5 whitespace-pre-wrap font-sans text-muted-foreground leading-relaxed max-h-40 overflow-y-auto">
                      {selectedTpl.bodyTemplate}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* Rendered sequence timeline — same cards as AI Generate tab */}
          {tplSequences.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm">
                  {tplMode === 'manual' ? 'Rendered Touch' : 'Generated Sequence'}
                  <span className="ml-2 text-xs text-muted-foreground font-normal">
                    ({tplSequences.length} {tplSequences.length === 1 ? 'touch' : 'touches'} — review and send)
                  </span>
                </h4>
              </div>

              <div className="relative">
                <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />

                {tplSequences.map((seq, i) => {
                  const wc        = wordCount(seq.bodyCopy);
                  const limit     = WORD_LIMITS[seq.angle] ?? 300;
                  const over      = wc > limit;
                  const isSavingT = savingId === seq.id;
                  const isSendingT = sendingId === seq.id;

                  return (
                    <div key={seq.id} className="relative pl-14 pb-6">
                      <div className={`absolute left-4 h-5 w-5 rounded-full flex items-center justify-center text-xs font-bold ${
                        seq.status === 'Scheduled'
                          ? 'bg-amber-500 text-white'
                          : seq.status === 'Sent'
                            ? 'bg-blue-500 text-white'
                            : 'bg-violet-500 text-white'
                      }`}>
                        {seq.touchNumber}
                      </div>

                      <Card className={seq.status === 'Scheduled' ? 'border-amber-200' : 'border-violet-100'}>
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between gap-2 flex-wrap">
                            <div>
                              <CardTitle className="text-sm flex items-center gap-2">
                                Touch {seq.touchNumber}
                                {tplMode === 'manual' && (
                                  <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
                                    Template
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
                              rows={6}
                              className="text-sm font-mono"
                              placeholder="Email body..."
                            />
                            <div className="flex justify-between text-xs">
                              <span className={over ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
                                Words: {wc}{over && ` — over ${limit} limit`}
                              </span>
                            </div>
                          </div>

                          <div className="flex gap-2 flex-wrap">
                            <TBtn
                              size="sm"
                              variant="outline"
                              tooltip="Save edits to this touch"
                              onClick={() => handleTplSave(seq)}
                              disabled={isSavingT}
                            >
                              {isSavingT
                                ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                : <Save className="h-3 w-3 mr-1" />
                              }
                              Save
                            </TBtn>

                            <TBtn
                              size="sm"
                              variant="outline"
                              tooltip="Approve and schedule for automated sending"
                              onClick={() => handleTplApprove(seq, i)}
                              disabled={isSavingT || seq.status === 'Scheduled' || seq.status === 'Sent'}
                            >
                              <Clock className="h-3 w-3 mr-1" />
                              {seq.status === 'Scheduled' ? 'Scheduled' : seq.status === 'Sent' ? 'Sent' : 'Approve & Schedule'}
                            </TBtn>

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

                            <TBtn
                              size="sm"
                              variant="ghost"
                              tooltip="Send immediately via MailBridge"
                              onClick={() => handleTplSendNow(seq, i)}
                              disabled={isSendingT || seq.status === 'Sent'}
                            >
                              {isSendingT
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
          {tplSequences.length === 0 && !templateSendMut.isPending && !tplTemplateId && (
            <div className="py-16 text-center text-muted-foreground">
              <LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p className="text-sm">Select a campaign, prospect, and template above</p>
              <p className="text-xs mt-1">
                Choose Manual to send the template as-is, or LLM-Assisted to use it as a creative seed
              </p>
            </div>
          )}

        </TabsContent>
        {/* ── End Tab 2 ───────────────────────────────────────────────────── */}

      </Tabs>
    </div>
  );
}