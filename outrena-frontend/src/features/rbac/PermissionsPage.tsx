/**
 * PermissionsPage.tsx — RBAC permissions catalog + feature-permission matrix.
 *
 * Two tabs:
 *   1. "Catalog" — read-only grid of all permissions grouped by category
 *      (from GET /permissions).
 *   2. "Feature Matrix" — table of features (rows) × required-permission
 *      (editable dropdown for SUPER_ADMIN, read-only for TENANT_ADMIN).
 *      Source: GET /feature-permissions, PUT /feature-permissions/{feature_key}.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Lock, Save } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { FeaturePermission, Permission } from "@/types/common";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { NativeSelect as Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const MOCK_PERMISSIONS: Permission[] = [
  { key: "prospects.read", display_name: "View prospects", description: "Read prospect records.", category: "Prospecting" },
  { key: "prospects.write", display_name: "Edit prospects", description: "Create/update prospects.", category: "Prospecting" },
  { key: "campaigns.read", display_name: "View campaigns", description: "Read campaigns.", category: "Outreach" },
  { key: "campaigns.write", display_name: "Manage campaigns", description: "Create/update campaigns.", category: "Outreach" },
  { key: "sequences.send", display_name: "Send sequences", description: "Schedule + send sequences.", category: "Outreach" },
  { key: "analytics.read", display_name: "View analytics", description: "Read analytics dashboards.", category: "Optimize" },
  { key: "users.manage", display_name: "Manage users", description: "Invite / deactivate users.", category: "Admin" },
  { key: "billing.manage", display_name: "Manage billing", description: "Update subscription.", category: "Admin" },
];

const MOCK_FEATURE_PERMISSIONS: FeaturePermission[] = [
  { feature_key: "autopilot", required_permission: "prospects.write", description: "Run prospecting autopilot." },
  { feature_key: "icp_profiles", required_permission: "prospects.write", description: "Manage ICP profiles." },
  { feature_key: "campaigns", required_permission: "campaigns.write", description: "Manage campaigns." },
  { feature_key: "email_studio", required_permission: "sequences.send", description: "Generate / approve sequences." },
  { feature_key: "analytics", required_permission: "analytics.read", description: "View analytics." },
  { feature_key: "user_management", required_permission: "users.manage", description: "Invite / manage users." },
  { feature_key: "billing", required_permission: "billing.manage", description: "Manage subscription." },
];

export function PermissionsPage() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const { data: permissions, isLoading: permsLoading } = useQuery({
    queryKey: ["permissions"],
    queryFn: () => http.get<Permission[]>("/api/v1/permissions"),
  });
  const { data: featurePerms, isLoading: fpLoading } = useQuery({
    queryKey: ["feature-permissions"],
    queryFn: () => http.get<FeaturePermission[]>("/api/v1/feature-permissions"),
  });

  const permList = permissions ?? MOCK_PERMISSIONS;
  const fpList = featurePerms ?? MOCK_FEATURE_PERMISSIONS;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Permissions"
        description="Browse the permission catalog and configure per-feature permission gates."
      />

      <Tabs defaultValue="catalog">
        <TabsList>
          <TabsTrigger value="catalog">
            <KeyRound className="mr-1.5 h-4 w-4" />
            Catalog
          </TabsTrigger>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="matrix">
                <Lock className="mr-1.5 h-4 w-4" />
                Feature Matrix
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>Feature × permission matrix — map each feature to the permission required to use it.</TooltipContent>
          </Tooltip>
        </TabsList>

        <TabsContent value="catalog" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Permission Catalog</CardTitle>
              <CardDescription>
                Read-only. {permList.length} permission
                {permList.length === 1 ? "" : "s"} across{" "}
                {new Set(permList.map((p) => p.category)).size} categories.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {permsLoading ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
              ) : (
                <CatalogGrid permissions={permList} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="matrix" className="space-y-4">
          <FeatureMatrixTable
            featurePerms={fpList}
            permissions={permList}
            loading={fpLoading}
            editable={isSuperAdmin}
          />
          {!isSuperAdmin && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Lock className="h-3 w-3" />
              Editing the feature-permission matrix requires SUPER_ADMIN role.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CatalogGrid({ permissions }: { permissions: Permission[] }) {
  const grouped = useMemo(() => {
    const map = new Map<string, Permission[]>();
    for (const p of permissions) {
      const list = map.get(p.category) ?? [];
      list.push(p);
      map.set(p.category, list);
    }
    return Array.from(map.entries());
  }, [permissions]);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {grouped.map(([category, perms]) => (
        <div key={category} className="rounded-lg border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {category}
          </p>
          <ul className="mt-3 space-y-2">
            {perms.map((p) => (
              <li key={p.key}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{p.display_name}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">
                      {p.key}
                    </p>
                    {p.description && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {p.description}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function FeatureMatrixTable({
  featurePerms,
  permissions,
  loading,
  editable,
}: {
  featurePerms: FeaturePermission[];
  permissions: Permission[];
  loading: boolean;
  editable: boolean;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const updateMutation = useMutation({
    mutationFn: ({ key, perm }: { key: string; perm: string }) =>
      http.put(`/api/v1/feature-permissions/${key}`, {
        required_permission: perm,
      }),
    onSuccess: () => {
      toast.success("Feature permission updated");
      queryClient.invalidateQueries({ queryKey: ["feature-permissions"] });
      setDirty((prev) => {
        const next = new Set(prev);
        next.delete(
          Object.entries(draft).find(([, v]) => v)?.[0] ?? "",
        );
        return next;
      });
    },
    onError: () => toast.error("Failed to update feature permission"),
  });

  function change(featureKey: string, perm: string) {
    setDraft((prev) => ({ ...prev, [featureKey]: perm }));
    setDirty((prev) => new Set(prev).add(featureKey));
  }

  function save(featureKey: string) {
    const perm = draft[featureKey];
    if (!perm) return;
    updateMutation.mutate({ key: featureKey, perm });
  }

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feature → Permission Matrix</CardTitle>
        <CardDescription>
          Required permission for each feature. {editable ? "Editable (SUPER_ADMIN)." : "Read-only."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Feature</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Required Permission</TableHead>
              <TableHead className="text-right">{editable ? "Action" : ""}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {featurePerms.map((fp) => {
              const currentValue = draft[fp.feature_key] ?? fp.required_permission;
              const isDirty = dirty.has(fp.feature_key);
              return (
                <TableRow key={fp.feature_key}>
                  <TableCell className="font-mono text-xs">
                    {fp.feature_key}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fp.description}
                  </TableCell>
                  <TableCell>
                    {editable ? (
                      <Select
                        value={currentValue}
                        onChange={(e) => change(fp.feature_key, e.target.value)}
                        className={cn("max-w-xs", isDirty && "border-primary")}
                      >
                        {permissions.map((p) => (
                          <option key={p.key} value={p.key}>
                            {p.display_name} ({p.key})
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <Badge variant="secondary">{fp.required_permission}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {editable && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!isDirty || updateMutation.isPending}
                        onClick={() => save(fp.feature_key)}
                      >
                        <Save className="h-3.5 w-3.5" />
                        Save
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
