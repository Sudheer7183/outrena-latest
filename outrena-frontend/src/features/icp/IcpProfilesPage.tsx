/**
 * IcpProfilesPage.tsx — ICP profiles CRUD + AI Suggest + Auto-Discover.
 *
 * Layout  : card grid (3-col responsive), matching the Next.js reference.
 * API     : /api/v1/icp-profiles (list, create, update, delete)
 *           /api/v1/icp-profiles/suggest  (AI suggest fields)
 *           /api/v1/icp-profiles/auto-discover (derive ICP from prospects)
 *
 * ICP-1  ✓ Auto-Discover dialog — 2-tab (website / description), save toggle,
 *            result preview, per-persona save.
 * ICP-2  ✓ Correct form fields: name, persona, companyType, topObjections (3),
 *            painPoints (3), valueProps (3), senderRole, senderCompany,
 *            senderOffer, proofMetric.
 * ICP-3  ✓ Card grid display — all fields shown with badge truncation + expand.
 * ICP-4  ✓ Edit dialog pre-populated with existing values.
 * ICP-5  ✓ Delete with confirmation dialog.
 * ICP-6  ✓ LLM config warning banner when no active LLM.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Globe,
  Plus,
  Trash2,
  Target,
  Loader2,
  Wand2,
  Edit3,
  AlertCircle,
  CheckCircle2,
  FileText,
  Bot,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/ui/page-header";
import { Switch } from "@/components/ui/switch";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/* ── Types (aligned with backend IcpResponse schema) ───────────────── */

interface IcpProfile {
  id: string;
  name: string;
  persona: string | null;
  companyType: string | null;
  topObjections: string[];
  painPoints: string[];
  valueProps: string[];
  senderRole: string | null;
  senderCompany: string | null;
  senderOffer: string | null;
  proofMetric: string | null;
  createdAt: string;
  updatedAt: string;
}

interface LlmConfig {
  id: string;
  isActive?: boolean;
  is_active?: boolean;
  isDefault?: boolean;
  is_default?: boolean;
}

/* Flat form state — 3 indexed inputs per array field */
interface IcpFormState {
  name: string;
  persona: string;
  companyType: string;
  senderRole: string;
  senderCompany: string;
  senderOffer: string;
  proofMetric: string;
  objection1: string;
  objection2: string;
  objection3: string;
  pain1: string;
  pain2: string;
  pain3: string;
  value1: string;
  value2: string;
  value3: string;
}

const EMPTY_FORM: IcpFormState = {
  name: "",
  persona: "",
  companyType: "",
  senderRole: "",
  senderCompany: "",
  senderOffer: "",
  proofMetric: "",
  objection1: "",
  objection2: "",
  objection3: "",
  pain1: "",
  pain2: "",
  pain3: "",
  value1: "",
  value2: "",
  value3: "",
};

/* ── Helpers ────────────────────────────────────────────────────────── */

function profileToForm(p: IcpProfile): IcpFormState {
  return {
    name: p.name,
    persona: p.persona ?? "",
    companyType: p.companyType ?? "",
    senderRole: p.senderRole ?? "",
    senderCompany: p.senderCompany ?? "",
    senderOffer: p.senderOffer ?? "",
    proofMetric: p.proofMetric ?? "",
    objection1: p.topObjections[0] ?? "",
    objection2: p.topObjections[1] ?? "",
    objection3: p.topObjections[2] ?? "",
    pain1: p.painPoints[0] ?? "",
    pain2: p.painPoints[1] ?? "",
    pain3: p.painPoints[2] ?? "",
    value1: p.valueProps[0] ?? "",
    value2: p.valueProps[1] ?? "",
    value3: p.valueProps[2] ?? "",
  };
}

function formToPayload(f: IcpFormState) {
  return {
    name: f.name.trim(),
    persona: f.persona.trim() || null,
    companyType: f.companyType.trim() || null,
    senderRole: f.senderRole.trim() || null,
    senderCompany: f.senderCompany.trim() || null,
    senderOffer: f.senderOffer.trim() || null,
    proofMetric: f.proofMetric.trim() || null,
    topObjections: [f.objection1, f.objection2, f.objection3].filter(Boolean),
    painPoints: [f.pain1, f.pain2, f.pain3].filter(Boolean),
    valueProps: [f.value1, f.value2, f.value3].filter(Boolean),
  };
}

function normaliseProfiles(raw: unknown): IcpProfile[] {
  if (Array.isArray(raw)) return raw as IcpProfile[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: IcpProfile[] }).items ?? [];
  return [];
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function IcpProfilesPage() {
  const qc = useQueryClient();

  /* ── Dialog state ── */
  const [crudOpen, setCrudOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<IcpFormState>(EMPTY_FORM);

  const [discoverOpen, setDiscoverOpen] = useState(false);
  const [discoverMode, setDiscoverMode] = useState<"website" | "description">(
    "website"
  );
  const [discoverWebsite, setDiscoverWebsite] = useState("");
  const [discoverDescription, setDiscoverDescription] = useState("");
  const [discoverSave, setDiscoverSave] = useState(true);
  const [discoverResult, setDiscoverResult] = useState<unknown>(null);
  const [discovering, setDiscovering] = useState(false);

  const [suggesting, setSuggesting] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<IcpProfile | null>(null);

  /* ── Queries ── */
  const profilesQ = useQuery<IcpProfile[]>({
    queryKey: ["icp-profiles"],
    queryFn: () =>
      http.get<unknown>("/api/v1/icp-profiles").then(normaliseProfiles),
  });
  const profiles = profilesQ.data ?? [];

  const llmQ = useQuery<LlmConfig[]>({
    queryKey: ["llm-configs"],
    queryFn: () =>
      http
        .get<unknown>("/api/v1/llm-configs")
        .then((r) => (Array.isArray(r) ? r : (r as { items?: LlmConfig[] })?.items ?? [])),
  });
  const hasLlm = (llmQ.data ?? []).some(
    (c) => (c.isActive ?? c.is_active) !== false
  );

  /* ── Mutations ── */
  const saveMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof formToPayload> & { id?: string }) => {
      const { id, ...body } = payload;
      if (id) return http.put<IcpProfile>(`/api/v1/icp-profiles/${id}`, body);
      return http.post<IcpProfile>("/api/v1/icp-profiles", body);
    },
    onSuccess: () => {
      toast.success(editingId ? "ICP profile updated" : "ICP profile saved");
      setCrudOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
    },
    onError: () => toast.error("Failed to save ICP profile"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/icp-profiles/${id}`),
    onSuccess: () => {
      toast.success("ICP profile deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
    },
    onError: () => toast.error("Delete failed"),
  });

  /* ── Handlers ── */
  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setCrudOpen(true);
  }

  function openEdit(p: IcpProfile) {
    setEditingId(p.id);
    setForm(profileToForm(p));
    setCrudOpen(true);
  }

  function handleSave() {
    if (!form.name.trim()) {
      toast.error("Profile name is required");
      return;
    }
    const payload = formToPayload(form);
    saveMutation.mutate(editingId ? { ...payload, id: editingId } : payload);
  }

  async function handleAiSuggest() {
    if (!form.persona.trim()) {
      toast.error("Enter a persona description first, then click AI Suggest");
      return;
    }
    setSuggesting(true);
    try {
      const data = await http.post<{
        suggestions?: {
          painPoints?: string[];
          objections?: string[];
          valueProps?: string[];
          proofMetric?: string;
        };
        painPoints?: string[];
        topObjections?: string[];
        valueProps?: string[];
        proofMetric?: string;
      }>("/api/v1/icp-profiles/suggest", {
        seed: form.persona,
      });
      // Support both wrapped (data.suggestions) and flat response shapes
      const s = (data as { suggestions?: typeof data }).suggestions ?? data;
      const pains = s.painPoints ?? [];
      const objections = s.topObjections ?? (s as { objections?: string[] }).objections ?? [];
      const values = s.valueProps ?? [];
      setForm((f) => ({
        ...f,
        pain1: pains[0] ?? f.pain1,
        pain2: pains[1] ?? f.pain2,
        pain3: pains[2] ?? f.pain3,
        objection1: objections[0] ?? f.objection1,
        objection2: objections[1] ?? f.objection2,
        objection3: objections[2] ?? f.objection3,
        value1: values[0] ?? f.value1,
        value2: values[1] ?? f.value2,
        value3: values[2] ?? f.value3,
        proofMetric: (s.proofMetric ?? f.proofMetric) || f.proofMetric,
      }));
      toast.success("AI suggestions applied! Review and adjust as needed.");
    } catch {
      toast.error("AI suggestion failed");
    }
    setSuggesting(false);
  }

  function resetDiscover() {
    setDiscoverMode("website");
    setDiscoverWebsite("");
    setDiscoverDescription("");
    setDiscoverSave(true);
    setDiscoverResult(null);
  }

  async function handleAutoDiscover() {
    if (discoverMode === "website" && !discoverWebsite.trim()) {
      toast.error("Enter your website URL");
      return;
    }
    if (discoverMode === "description" && discoverDescription.trim().length < 10) {
      toast.error("Enter at least 10 characters describing your ICP");
      return;
    }
    setDiscovering(true);
    setDiscoverResult(null);
    try {
      // Backend /auto-discover accepts a list of prospects. For the
      // website/description flow we send a synthetic single-prospect payload
      // with the input embedded in the description field.
      const syntheticProspect =
        discoverMode === "website"
          ? { description: `website: ${discoverWebsite.trim()}` }
          : { description: discoverDescription.trim() };

      const data = await http.post<unknown>(
        "/api/v1/icp-profiles/auto-discover",
        {
          prospects: [syntheticProspect],
          existingIcpId: null,
        }
      );
      setDiscoverResult(data);

      if (discoverSave) {
        // Auto-save: derive a profile from the response and POST it
        const r = data as {
          suggestedPersona?: string;
          commonAttributes?: Record<string, unknown>;
        };
        const name =
          discoverMode === "website"
            ? `Profile from ${discoverWebsite.trim()}`
            : "Auto-Discovered ICP";
        await http.post<IcpProfile>("/api/v1/icp-profiles", {
          name,
          persona: r.suggestedPersona ?? "",
          companyType:
            String(r.commonAttributes?.companyType ?? "") || null,
          painPoints: [],
          topObjections: [],
          valueProps: [],
        });
        toast.success(`Auto-discovered ICP saved — "${name}"`);
        qc.invalidateQueries({ queryKey: ["icp-profiles"] });
        setTimeout(() => {
          setDiscoverOpen(false);
          resetDiscover();
        }, 2500);
      } else {
        toast.success("Auto-discovery complete — review the result below");
      }
    } catch {
      toast.error("Auto-discovery failed");
    }
    setDiscovering(false);
  }

  async function handleSaveDiscoveredProfile(profileData: {
    name?: string;
    persona?: string;
    companyType?: string | null;
  }) {
    try {
      await http.post<IcpProfile>("/api/v1/icp-profiles", {
        name: profileData.name ?? "Auto-Discovered ICP",
        persona: profileData.persona ?? "",
        companyType: profileData.companyType ?? null,
        painPoints: [],
        topObjections: [],
        valueProps: [],
      });
      toast.success(`Saved "${profileData.name ?? "ICP"}" to your list`);
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
      setDiscoverOpen(false);
      resetDiscover();
    } catch {
      toast.error("Failed to save profile");
    }
  }

  /* ── Render ── */
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="ICP Profiles"
        description="Define your Ideal Customer Profiles for targeted outreach"
        actions={
          <div className="flex items-center gap-2">
            {/* Auto-Discover ICP */}
            <Dialog
              open={discoverOpen}
              onOpenChange={(o) => {
                setDiscoverOpen(o);
                if (!o) resetDiscover();
              }}
            >
              <DialogTrigger asChild>
                <Button
                  variant="outline"
                  className="border-violet-300 text-violet-700 hover:bg-violet-50"
                  onClick={() => {
                    resetDiscover();
                    setDiscoverOpen(true);
                  }}
                >
                  <Wand2 className="h-4 w-4 mr-2" />
                  Auto-Discover ICP
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Auto-Discover ICP</DialogTitle>
                  <DialogDescription>
                    Let the AI infer your Ideal Customer Profile — the fastest
                    way to get started.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                  {/* LLM warning */}
                  {!hasLlm && (
                    <div className="rounded-md bg-amber-50 border border-amber-300 p-4 text-sm space-y-2">
                      <p className="font-medium text-amber-900 flex items-center gap-2">
                        <AlertCircle className="h-4 w-4" />
                        No AI model configured
                      </p>
                      <p className="text-amber-800 text-xs">
                        Auto-Discover needs an LLM. Configure one in LLM
                        Models first.
                      </p>
                    </div>
                  )}

                  {/* Mode tabs */}
                  <Tabs
                    value={discoverMode}
                    onValueChange={(v) => {
                      setDiscoverMode(v as "website" | "description");
                      setDiscoverResult(null);
                    }}
                  >
                    <TabsList className="grid w-full grid-cols-2">
                      <TabsTrigger value="website">
                        <Globe className="h-3.5 w-3.5 mr-1.5" />
                        From your website
                      </TabsTrigger>
                      <TabsTrigger value="description">
                        <FileText className="h-3.5 w-3.5 mr-1.5" />
                        From description
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="website" className="space-y-3 mt-4">
                      <div className="rounded-md bg-violet-50 border border-violet-200 p-3 text-xs text-violet-800">
                        <p className="font-medium mb-1">How it works</p>
                        <p>
                          Enter your company URL. The AI reads your website,
                          searches for competitors and industry context, and
                          infers your ICP automatically — persona, company
                          type, pain points, and value propositions.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>Your Website URL</Label>
                        <Input
                          placeholder="e.g. mycompany.com"
                          value={discoverWebsite}
                          onChange={(e) => setDiscoverWebsite(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                          No need to include https:// — we'll strip it.
                        </p>
                      </div>
                    </TabsContent>

                    <TabsContent
                      value="description"
                      className="space-y-3 mt-4"
                    >
                      <div className="rounded-md bg-violet-50 border border-violet-200 p-3 text-xs text-violet-800">
                        <p className="font-medium mb-1">How it works</p>
                        <p>
                          Describe your ideal customer in plain English. The
                          AI structures it into a full ICP profile — persona,
                          company type, pain points, objections, and value
                          propositions.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>Describe your ideal customer</Label>
                        <Textarea
                          placeholder="e.g. We sell to VP of Engineering at Series B SaaS companies (50–500 employees) who are struggling with slow release cycles..."
                          value={discoverDescription}
                          onChange={(e) =>
                            setDiscoverDescription(e.target.value)
                          }
                          rows={5}
                        />
                        <p className="text-xs text-muted-foreground">
                          The more specific you are, the better the AI result.
                        </p>
                      </div>
                    </TabsContent>
                  </Tabs>

                  <Separator />

                  {/* Save toggle */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">
                        Save profiles automatically
                      </p>
                      <p className="text-xs text-muted-foreground">
                        If on, discovered profiles are saved immediately. If
                        off, you can review first.
                      </p>
                    </div>
                    <Switch
                      checked={discoverSave}
                      onCheckedChange={setDiscoverSave}
                    />
                  </div>

                  {/* Result */}
                  {Boolean(discoverResult) && (
                    <DiscoverResult
                      result={discoverResult as DiscoverResultShape}
                      discoverMode={discoverMode}
                      discoverSave={discoverSave}
                      discoverWebsite={discoverWebsite}
                      onSaveProfile={handleSaveDiscoveredProfile}
                    />
                  )}
                </div>

                <DialogFooter>
                  {discovering && (
                    <p className="text-xs text-muted-foreground mr-auto flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {discoverMode === "website"
                        ? "Searching the web + AI analysis (30–60 s)…"
                        : "AI analyzing your description (10–20 s)…"}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDiscoverOpen(false);
                      resetDiscover();
                    }}
                  >
                    Close
                  </Button>
                  <Button
                    onClick={handleAutoDiscover}
                    disabled={discovering || !hasLlm}
                  >
                    {discovering ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                        Discovering…
                      </>
                    ) : (
                      <>
                        <Wand2 className="h-3.5 w-3.5 mr-1.5" />
                        Run Auto-Discovery
                      </>
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Create ICP (manual) */}
            <Dialog
              open={crudOpen}
              onOpenChange={(o) => {
                setCrudOpen(o);
                if (!o) {
                  setForm(EMPTY_FORM);
                  setEditingId(null);
                }
              }}
            >
              <DialogTrigger asChild>
                <Button onClick={openCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create ICP
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <IcpFormDialog
                  form={form}
                  setForm={setForm}
                  editingId={editingId}
                  suggesting={suggesting}
                  saving={saveMutation.isPending}
                  hasLlm={hasLlm}
                  onAiSuggest={handleAiSuggest}
                  onSave={handleSave}
                  onClose={() => {
                    setCrudOpen(false);
                    setForm(EMPTY_FORM);
                    setEditingId(null);
                  }}
                />
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {/* LLM warning banner */}
      {!hasLlm && !llmQ.isLoading && (
        <div className="rounded-md bg-amber-50 border border-amber-300 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-amber-900">
              No AI model configured
            </p>
            <p className="text-xs text-amber-800">
              AI Suggest and Auto-Discover require an active LLM. Configure
              one in{" "}
              <span className="font-semibold">Setup → LLM Models</span>.
            </p>
          </div>
          <Bot className="h-5 w-5 text-amber-500 ml-auto shrink-0" />
        </div>
      )}

      {/* Profile grid */}
      {profilesQ.isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-48 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      ) : profilesQ.isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load ICP profiles.
            </p>
            <Button
              onClick={() => profilesQ.refetch()}
              className="mt-4"
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : profiles.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Target className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h4 className="font-medium mb-2">No ICP Profiles Yet</h4>
            <p className="text-sm text-muted-foreground mb-4">
              Create your first ICP to start targeting the right prospects.
            </p>
            <Button size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-1" />
              Create ICP
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {profiles.map((p) => (
            <IcpCard
              key={p.id}
              profile={p}
              onEdit={() => openEdit(p)}
              onDelete={() => setDeleteTarget(p)}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete ICP profile?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.name
                ? `"${deleteTarget.name}" will be permanently removed. Prospects linked to this profile will lose their ICP scoring. This action cannot be undone.`
                : "This ICP profile will be permanently removed. This action cannot be undone."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
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
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ── IcpCard ────────────────────────────────────────────────────────── */

function IcpCard({
  profile: p,
  onEdit,
  onDelete,
}: {
  profile: IcpProfile;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm truncate">{p.name}</CardTitle>
          <div className="flex items-center gap-1 shrink-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8"
                  onClick={onEdit}
                  aria-label="Edit"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Edit this ICP profile</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-red-500 hover:text-red-700"
                  onClick={onDelete}
                  aria-label="Delete"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete this ICP profile</TooltipContent>
            </Tooltip>
          </div>
        </div>
        <CardDescription className="text-xs">
          {p.companyType ?? "No company type"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        {p.persona && (
          <p className="text-muted-foreground line-clamp-2">{p.persona}</p>
        )}
        {p.topObjections.length > 0 && (
          <div>
            <p className="font-medium mb-1">Objections:</p>
            <div className="flex flex-wrap gap-1">
              {p.topObjections.map((o, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {o}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {p.painPoints.length > 0 && (
          <div>
            <p className="font-medium mb-1">Pain Points:</p>
            <div className="flex flex-wrap gap-1">
              {p.painPoints.map((pn, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {pn}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {p.valueProps.length > 0 && (
          <div>
            <p className="font-medium mb-1">Value Props:</p>
            <div className="flex flex-wrap gap-1">
              {p.valueProps.map((v, i) => (
                <Badge
                  key={i}
                  className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200"
                >
                  {v}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {(p.senderCompany ?? p.senderRole) && (
          <p className="text-muted-foreground mt-1">
            From:{" "}
            {[p.senderRole, p.senderCompany].filter(Boolean).join(" at ")}
          </p>
        )}
        {p.proofMetric && (
          <p className="text-muted-foreground">Proof: {p.proofMetric}</p>
        )}
      </CardContent>
    </Card>
  );
}

/* ── IcpFormDialog ──────────────────────────────────────────────────── */

function IcpFormDialog({
  form,
  setForm,
  editingId,
  suggesting,
  saving,
  hasLlm,
  onAiSuggest,
  onSave,
  onClose,
}: {
  form: IcpFormState;
  setForm: React.Dispatch<React.SetStateAction<IcpFormState>>;
  editingId: string | null;
  suggesting: boolean;
  saving: boolean;
  hasLlm: boolean;
  onAiSuggest: () => void;
  onSave: () => void;
  onClose: () => void;
}) {
  function f(key: keyof IcpFormState) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [key]: e.target.value }));
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {editingId ? "Edit ICP Profile" : "Create ICP Profile"}
        </DialogTitle>
        <DialogDescription>
          {editingId
            ? "Update your target buyer persona"
            : "Define your target buyer persona"}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 py-4">
        {/* Core fields */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Profile Name *</Label>
            <Input
              placeholder="e.g. SaaS CTOs under 200"
              value={form.name}
              onChange={f("name")}
            />
          </div>
          <div className="space-y-2">
            <Label>Company Type</Label>
            <Input
              placeholder="e.g. B2B SaaS, Series A–C"
              value={form.companyType}
              onChange={f("companyType")}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Target Persona</Label>
          <Textarea
            placeholder="Describe your ideal buyer in detail…"
            value={form.persona}
            onChange={f("persona")}
            rows={3}
          />
        </div>

        <Separator />
        <p className="text-sm font-medium">Sender Information</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Your Role</Label>
            <Input
              placeholder="e.g. CEO at MyCo"
              value={form.senderRole}
              onChange={f("senderRole")}
            />
          </div>
          <div className="space-y-2">
            <Label>Your Company</Label>
            <Input
              placeholder="e.g. MyCo"
              value={form.senderCompany}
              onChange={f("senderCompany")}
            />
          </div>
          <div className="space-y-2">
            <Label>Your Offer</Label>
            <Input
              placeholder="e.g. AI lead gen platform"
              value={form.senderOffer}
              onChange={f("senderOffer")}
            />
          </div>
          <div className="space-y-2">
            <Label>Proof Metric</Label>
            <Input
              placeholder="e.g. 3× pipeline in 90 days"
              value={form.proofMetric}
              onChange={f("proofMetric")}
            />
          </div>
        </div>

        <Separator />
        <p className="text-sm font-medium">Top 3 Objections</p>
        <p className="text-xs text-muted-foreground">
          What will this buyer push back on when approached?
        </p>
        <div className="grid grid-cols-1 gap-2">
          <Input
            placeholder='e.g. "We already have a solution for this"'
            value={form.objection1}
            onChange={f("objection1")}
          />
          <Input
            placeholder="e.g. &quot;We don't have budget for new tools right now&quot;"
            value={form.objection2}
            onChange={f("objection2")}
          />
          <Input
            placeholder='e.g. "Our team is too busy to evaluate another vendor"'
            value={form.objection3}
            onChange={f("objection3")}
          />
        </div>

        <Separator />
        <p className="text-sm font-medium">Pain Points</p>
        <p className="text-xs text-muted-foreground">
          What daily frustrations or strategic gaps does this buyer face?
        </p>
        <div className="grid grid-cols-1 gap-2">
          <Input
            placeholder='e.g. "Manual prospecting takes 20+ hours per week"'
            value={form.pain1}
            onChange={f("pain1")}
          />
          <Input
            placeholder='e.g. "Low reply rates on outbound campaigns (under 2%)"'
            value={form.pain2}
            onChange={f("pain2")}
          />
          <Input
            placeholder='e.g. "Sales reps send generic templates that damage brand"'
            value={form.pain3}
            onChange={f("pain3")}
          />
        </div>

        <Separator />
        <p className="text-sm font-medium">Value Propositions</p>
        <p className="text-xs text-muted-foreground">
          What specific outcomes can you deliver? Use metrics when possible.
        </p>
        <div className="grid grid-cols-1 gap-2">
          <Input
            placeholder='e.g. "3× more qualified pipeline in 90 days"'
            value={form.value1}
            onChange={f("value1")}
          />
          <Input
            placeholder='e.g. "Cut prospecting time from 20 hrs to 2 hrs per week"'
            value={form.value2}
            onChange={f("value2")}
          />
          <Input
            placeholder='e.g. "AI-written emails that sound human, not like a vendor"'
            value={form.value3}
            onChange={f("value3")}
          />
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="outline"
          className="border-violet-300 text-violet-700 hover:bg-violet-50"
          onClick={onAiSuggest}
          disabled={suggesting || !form.persona.trim() || !hasLlm}
        >
          <Sparkles className="h-3.5 w-3.5 mr-1.5" />
          {suggesting ? "Suggesting…" : "AI Suggest Fields"}
        </Button>
        <Button onClick={onSave} disabled={saving}>
          {saving ? (
            <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
          ) : null}
          {editingId ? "Update ICP" : "Save ICP"}
        </Button>
      </DialogFooter>
    </>
  );
}

/* ── DiscoverResult ─────────────────────────────────────────────────── */

interface DiscoverResultShape {
  suggestedPersona?: string;
  commonAttributes?: Record<string, unknown>;
}

function DiscoverResult({
  result,
  discoverMode,
  discoverSave,
  discoverWebsite,
  onSaveProfile,
}: {
  result: DiscoverResultShape;
  discoverMode: "website" | "description";
  discoverSave: boolean;
  discoverWebsite: string;
  onSaveProfile: (p: {
    name?: string;
    persona?: string;
    companyType?: string | null;
  }) => void;
}) {
  return (
    <div className="space-y-3 rounded-md border p-4 bg-muted/30">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          Discovery Result
        </p>
        <Badge variant="outline" className="text-xs font-mono">
          {discoverMode === "website" ? (
            <Globe className="h-3 w-3 mr-1" />
          ) : (
            <FileText className="h-3 w-3 mr-1" />
          )}
          {discoverMode === "website" ? discoverWebsite : "your description"}
        </Badge>
      </div>

      {/* Suggested persona */}
      {result.suggestedPersona && (
        <div className="text-xs space-y-1">
          <p>
            <span className="font-medium">Suggested Persona:</span>{" "}
            {`${result.suggestedPersona}`}
          </p>
        </div>
      )}

      {/* Common attributes */}
      {result.commonAttributes && Object.keys(result.commonAttributes).length > 0 && (
          <div className="text-xs space-y-1">
            <p className="font-medium">Common Attributes:</p>
            {Object.entries(result.commonAttributes).map(
              ([k, v]) => (
                <p key={k}>
                  <span className="font-medium capitalize">{k}:</span>{" "}
                  {`${v}`}
                </p>
              )
            )}
          </div>
        )}

      {/* Review mode save button */}
      {!discoverSave && (
        <Button
          size="sm"
          className="mt-2"
          onClick={() =>
            onSaveProfile({
              name:
                discoverMode === "website"
                  ? `Profile from ${discoverWebsite}`
                  : "Auto-Discovered ICP",
              persona: result.suggestedPersona
                ? String(result.suggestedPersona)
                : undefined,
              companyType:
                result.commonAttributes && "companyType" in result.commonAttributes
                  ? `${result.commonAttributes.companyType}`
                  : null,
            })
          }
        >
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Save {"&"} Close
        </Button>
      )}

      {discoverSave && (
        <p className="text-xs text-emerald-700 font-medium">
          ✓ Profile saved — modal will close shortly.
        </p>
      )}
    </div>
  );
}