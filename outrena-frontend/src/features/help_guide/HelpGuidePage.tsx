/**
 * HelpGuidePage.tsx — role-filtered, deep-linkable, category-grouped
 * help guide for the OUTRENA SaaS platform.
 *
 * Primary data source: `GET /help/sections` (server filters by role) +
 * `GET /help/sections/{slug}` for articles. Includes live search via
 * `GET /help/search?q=`. Article bodies are rendered as GitHub-flavoured
 * Markdown via `react-markdown` + `remark-gfm`, with screenshot images
 * routed through `<HelpScreenshot>` (lazy-load + click-to-zoom +
 * "coming soon" placeholder).
 *
 * Deep-linking (AUDIT-HELP-1 / G-4): the route is registered as
 * `/help-guide/:sectionSlug?/:articleSlug?`. The page reads the URL
 * params via `useParams`, auto-selects the section, and auto-opens the
 * article. Clicking a section or article updates the URL via
 * `useNavigate` so the location is shareable + bookmarkable.
 *
 * Auth (G-5): the route is wrapped in `<ProtectedRoute minimumRole="REP">`
 * at the router level (see `routes/index.tsx`). Unauthenticated users
 * are redirected to `/login` before reaching this page.
 *
 * Static fallback (G-6): removed. The API is the source of truth. When
 * the API fails, the page shows a friendly error state with a retry
 * button — no static content that would bypass role filtering.
 *
 * Type alignment (G-3): the backend `HelpArticleResponse` now includes
 * `section_title` (joined from `help_sections`) so the search-result
 * badge renders the section name instead of `undefined`. See
 * `app/api/v1/help.py` + `app/services/help_service.py`.
 *
 * Category grouping (task 2-c enhancement): the sidebar groups the
 * role-filtered sections into 6 categories — Getting Started,
 * Prospecting & Outreach, Pipeline & Optimization, Admin & Billing,
 * Platform, Support — mirroring the SaaS sidebar nav-config. Each
 * group has a header; the user sees only the groups their role can
 * access (server-side filter already excludes gated sections, the
 * group simply renders whichever of its members survived).
 *
 * Screenshots (task 2-c enhancement, AUDIT-HELP-1 / H-3): markdown
 * image syntax `![alt](/help-screenshots/foo.png)` is intercepted by
 * `ArticleBody`'s `img` renderer and routed through `<HelpScreenshot>`,
 * which lazy-loads + shows a "coming soon" placeholder when the PNG
 * is missing + opens a click-to-zoom Dialog on click. To add a new
 * screenshot: drop the PNG into `/public/help-screenshots/` and
 * reference it from the article body — zero code changes required.
 *
 * Feedback widget (task 2-c enhancement, AUDIT-HELP-1 / H-7): each
 * open article shows a "Was this helpful?" thumbs-up/down row at the
 * bottom. The vote is logged locally (no backend yet — wire to a
 * future `POST /help/articles/{slug}/feedback` endpoint when ready).
 *
 * Role-aware UI (task 2-c enhancement): the page reads `useAuth()` to
 * show a small "Viewing as {role}" badge in the header and to label
 * gated sections in the sidebar. (Server-side filtering remains the
 * secure source of truth — the client-side badge is purely
 * informational.)
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  RefreshCw,
  Search,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { http } from "@/services/apiClient";
import type {
  HelpArticle,
  HelpSearchResult,
  HelpSection,
  HelpSectionDetail,
} from "@/types/common";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui/page-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpScreenshot } from "./HelpScreenshot";

/* ────────────────────────────────────────────────────────────────────────── */
/*  Sidebar category mapping                                                 */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Maps a help-section slug → sidebar category. Categories mirror the
 * SaaS nav-config group structure (Getting Started / Prospecting /
 * Outreach / Pipeline / Optimize / Setup / Admin / Platform / Support)
 * but consolidated to 6 to keep the sidebar short.
 *
 * Sections not in this map (e.g. a future `faq` slug) fall into
 * "Other". The order of `CATEGORIES` controls sidebar render order.
 */
const CATEGORIES: { id: string; label: string; slugs: string[] }[] = [
  {
    id: "getting-started",
    label: "Getting Started",
    slugs: ["getting-started"],
  },
  {
    id: "prospecting-outreach",
    label: "Prospecting & Outreach",
    slugs: [
      "icp-prospects",
      "campaigns-sequences",
      "deliverability",
      "integrations",
      "flows-autopilot",
      "linkedin-alumni",
    ],
  },
  {
    id: "pipeline-optimization",
    label: "Pipeline & Optimization",
    slugs: ["pipeline", "optimization"],
  },
  {
    id: "admin-billing",
    label: "Admin & Billing",
    slugs: ["admin-setup", "billing-rbac", "compliance-gdpr"],
  },
  {
    id: "platform",
    label: "Platform",
    slugs: ["platform-admin"],
  },
  {
    id: "support",
    label: "Support",
    slugs: ["support-help"],
  },
];

/**
 * Returns the category label for a section slug, or "Other" if unknown.
 * Used for sidebar grouping + ARIA labels.
 */
function categoryFor(slug: string): string {
  for (const c of CATEGORIES) {
    if (c.slugs.includes(slug)) return c.label;
  }
  return "Other";
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Article body (markdown renderer with screenshot + cross-link support)    */
/* ────────────────────────────────────────────────────────────────────────── */

/**
 * Markdown renderer for help-article bodies.
 *
 * Article bodies are stored as GFM markdown in `help_articles.body`.
 * Cross-article links use the `/help/<section>/<article>` URL
 * convention (also accepts `/help-guide/...`); `react-markdown`'s
 * default `<a>` renderer would do a full-page reload, so we override
 * `a` to use `react-router-dom`'s `navigate` for same-app navigation.
 *
 * Images are routed through `<HelpScreenshot>` for lazy-load +
 * click-to-zoom + "coming soon" placeholder (AUDIT-HELP-1 / H-3).
 */
function ArticleBody({
  body,
  onNavigate,
}: {
  body: string;
  onNavigate: (path: string) => void;
}) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:mb-2 prose-headings:mt-4 prose-p:my-2 prose-li:my-0.5 prose-a:text-primary prose-a:underline prose-strong:text-foreground prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:before:content-none prose-code:after:content-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children, ...rest }) {
            if (!href) return <a {...rest}>{children}</a>;
            // Internal deep-links (start with /help-guide/ or /help/)
            // route via navigate so we don't reload the page.
            if (
              href.startsWith("/help-guide/") ||
              href.startsWith("/help/")
            ) {
              return (
                <a
                  href={href}
                  onClick={(e) => {
                    e.preventDefault();
                    onNavigate(href.replace(/^\/help\//, "/help-guide/"));
                  }}
                >
                  {children}
                </a>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer" {...rest}>
                {children}
              </a>
            );
          },
          // Route markdown images through <HelpScreenshot> for
          // lazy-load + click-to-zoom + "coming soon" placeholder.
          img({ src, alt }) {
            const srcStr = typeof src === "string" ? src : "";
            if (!srcStr) return null;
            return (
              <HelpScreenshot
                src={srcStr}
                alt={alt ?? ""}
                caption={alt ?? undefined}
              />
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Article card (collapsible, with feedback widget)                         */
/* ────────────────────────────────────────────────────────────────────────── */

function ArticleCard({
  article,
  sectionSlug,
  isOpen,
  onToggle,
  onNavigate,
}: {
  article: HelpArticle;
  sectionSlug: string;
  isOpen: boolean;
  onToggle: () => void;
  onNavigate: (path: string) => void;
}) {
  const bodyRef = useRef<HTMLDivElement | null>(null);
  // Feedback state: null = not voted, true = helpful, false = not helpful.
  // Stored in localStorage keyed by article slug so the user sees their
  // prior vote on revisit. Wire to a backend endpoint when available.
  const feedbackKey = `help-feedback:${sectionSlug}:${article.slug}`;
  const [feedback, setFeedback] = useState<boolean | null>(() => {
    try {
      const stored = localStorage.getItem(feedbackKey);
      return stored === null ? null : stored === "true";
    } catch {
      return null;
    }
  });

  // Scroll the article into view when it opens (deep-link landing).
  useEffect(() => {
    if (isOpen && bodyRef.current) {
      bodyRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [isOpen]);

  const handleFeedback = (value: boolean) => {
    setFeedback(value);
    try {
      localStorage.setItem(feedbackKey, String(value));
    } catch {
      // localStorage may be unavailable (private mode / quota) —
      // silently drop; the vote still affects this session's UI.
    }
  };

  return (
    <div
      ref={bodyRef}
      className="scroll-mt-20 rounded-lg border bg-card"
    >
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 p-4 text-left"
        aria-expanded={isOpen}
      >
        <span className="text-sm font-semibold">{article.title}</span>
        <span className="text-xs text-muted-foreground">
          {isOpen ? "Hide" : "Show"}
        </span>
      </button>
      {isOpen && (
        <div className="border-t px-4 py-3 text-sm leading-relaxed text-muted-foreground">
          <ArticleBody body={article.body} onNavigate={onNavigate} />

          {/* Feedback widget (AUDIT-HELP-1 / H-7) */}
          <div className="mt-4 flex items-center gap-2 border-t pt-3">
            <span className="text-xs text-muted-foreground">
              Was this helpful?
            </span>
            <Button
              type="button"
              size="sm"
              variant={feedback === true ? "default" : "outline"}
              className="h-7 px-2"
              onClick={() => handleFeedback(true)}
              aria-pressed={feedback === true}
              aria-label="Mark as helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
              {feedback === true && <span className="ml-1 text-xs">Thanks</span>}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={feedback === false ? "default" : "outline"}
              className="h-7 px-2"
              onClick={() => handleFeedback(false)}
              aria-pressed={feedback === false}
              aria-label="Mark as not helpful"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
              {feedback === false && <span className="ml-1 text-xs">Noted</span>}
            </Button>
            {feedback !== null && (
              <span className="ml-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3 w-3" />
                Feedback saved
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Main page component                                                      */
/* ────────────────────────────────────────────────────────────────────────── */

export function HelpGuidePage() {
  const { sectionSlug, articleSlug } = useParams<{
    sectionSlug?: string;
    articleSlug?: string;
  }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  // Track whether the active section was explicitly chosen by the user
  // (vs. defaulted from the API). Used to decide whether to redirect the
  // URL when the sections list loads.
  const [userPickedSection, setUserPickedSection] = useState(false);

  // Debounce search input.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  // Fetch role-filtered sections.
  const {
    data: sections,
    isLoading: sectionsLoading,
    isError: sectionsError,
    refetch: refetchSections,
  } = useQuery({
    queryKey: ["help", "sections"],
    queryFn: () => http.get<HelpSection[]>("/api/v1/help/sections"),
    retry: false,
  });

  // Resolve the effective slug: URL param → user-pick → first section.
  const effectiveSlug = useMemo(() => {
    if (sectionSlug) return sectionSlug;
    if (userPickedSection) return "";
    if (sections && sections.length > 0) return sections[0].slug;
    return "";
  }, [sectionSlug, userPickedSection, sections]);

  // If the URL has no sectionSlug and we just loaded sections, sync the
  // URL to the first section so it's shareable.
  useEffect(() => {
    if (!sectionSlug && sections && sections.length > 0 && !userPickedSection) {
      navigate(`/help-guide/${sections[0].slug}`, { replace: true });
    }
  }, [sectionSlug, sections, userPickedSection, navigate]);

  // If the URL has a sectionSlug that isn't in the role-filtered list
  // (e.g. REP bookmarks a SUPER_ADMIN page), redirect to the first
  // visible section.
  useEffect(() => {
    if (
      sectionSlug &&
      sections &&
      sections.length > 0 &&
      !sections.some((s) => s.slug === sectionSlug)
    ) {
      navigate(`/help-guide/${sections[0].slug}`, { replace: true });
    }
  }, [sectionSlug, sections, navigate]);

  const { data: sectionDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["help", "section", effectiveSlug],
    queryFn: () =>
      http.get<HelpSectionDetail>(`/api/v1/help/sections/${effectiveSlug}`),
    enabled: !!effectiveSlug,
  });

  // Search query.
  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ["help", "search", debouncedSearch],
    queryFn: () =>
      http.get<HelpSearchResult[]>("/api/v1/help/search", {
        q: debouncedSearch,
      }),
    enabled: debouncedSearch.length >= 2,
  });

  const showSearch = debouncedSearch.length >= 2;

  // Group the role-filtered sections by category for the sidebar.
  // Sections whose slug isn't in any CATEGORIES bucket land in "Other".
  const groupedSections = useMemo(() => {
    if (!sections || sections.length === 0) return [];
    const bySlug = new Map(sections.map((s) => [s.slug, s]));
    const groups: { id: string; label: string; items: HelpSection[] }[] = [];
    for (const cat of CATEGORIES) {
      const items = cat.slugs
        .map((slug) => bySlug.get(slug))
        .filter((s): s is HelpSection => Boolean(s));
      if (items.length > 0) {
        groups.push({ id: cat.id, label: cat.label, items });
      }
    }
    // Catch-all: any section not in a known category.
    const knownSlugs = new Set(CATEGORIES.flatMap((c) => c.slugs));
    const other = sections.filter((s) => !knownSlugs.has(s.slug));
    if (other.length > 0) {
      groups.push({ id: "other", label: "Other", items: other });
    }
    return groups;
  }, [sections]);

  const handleSectionClick = (slug: string) => {
    setUserPickedSection(true);
    navigate(`/help-guide/${slug}`);
  };

  const handleArticleToggle = (articleSlugArg: string) => {
    if (!effectiveSlug) return;
    // Toggle: if the open articleSlug matches, close (drop the param);
    // otherwise open the new one.
    if (articleSlug === articleSlugArg) {
      navigate(`/help-guide/${effectiveSlug}`);
    } else {
      navigate(`/help-guide/${effectiveSlug}/${articleSlugArg}`);
    }
  };

  const handleNavigate = (path: string) => {
    // Internal cross-article link click from inside a markdown body.
    // Normalize /help/<section>/<article> → /help-guide/...
    navigate(path);
  };

  const roleLabel = user?.role ?? "REP";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Help Guide"
        description="Everything you need to master the OUTRENA outreach operating system."
        actions={
          <Badge variant="outline" className="hidden sm:inline-flex">
            Viewing as {roleLabel}
          </Badge>
        }
      />

      {/* Search */}
      <Card>
        <CardContent className="p-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search the help guide…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
              aria-label="Search help guide"
            />
          </div>
          {showSearch && (
            <div className="mt-3 space-y-2">
              {searchLoading ? (
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Searching…
                </p>
              ) : (searchResults ?? []).length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No results for &ldquo;{debouncedSearch}&rdquo;.
                </p>
              ) : (
                <ul className="space-y-1">
                  {(searchResults ?? []).map((r) => (
                    <li key={r.id}>
                      <button
                        onClick={() =>
                          navigate(`/help-guide/${r.section_slug}/${r.slug}`)
                        }
                        className="flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
                      >
                        <span className="font-medium">{r.title}</span>
                        <Badge variant="secondary">{r.section_title}</Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Body: error state | loading state | sections grid | empty state */}
      {sectionsError ? (
        <ErrorState onRetry={() => refetchSections()} />
      ) : sectionsLoading ? (
        <LoadingState />
      ) : !sections || sections.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          {/* Sections list (sidebar) — grouped by category */}
          <Card className="lg:col-span-1 lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <HelpCircle className="h-4 w-4" />
                Sections
              </CardTitle>
              <CardDescription className="text-xs">
                {sections.length} articles · filtered for {roleLabel}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <nav aria-label="Help guide sections">
                {groupedSections.map((group) => (
                  <div key={group.id} className="border-t first:border-t-0">
                    <p className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      {group.label}
                    </p>
                    <ul>
                      {(Array.isArray(group.items) ? group.items : []).map((s) => {
                        const isActive = effectiveSlug === s.slug;
                        return (
                          <li key={s.id}>
                            <button
                              onClick={() => handleSectionClick(s.slug)}
                              className={`flex w-full flex-col items-start gap-0.5 px-4 py-2.5 text-left transition-colors hover:bg-accent ${
                                isActive ? "bg-accent" : ""
                              }`}
                              aria-current={isActive ? "page" : undefined}
                            >
                              <span className="text-sm font-medium">
                                {s.title}
                              </span>
                              <span className="text-xs text-muted-foreground line-clamp-1">
                                {s.description}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </nav>
            </CardContent>
          </Card>

          {/* Section detail (articles) */}
          <Card className="lg:col-span-3">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle>
                    {sectionDetail?.title ?? "Loading…"}
                  </CardTitle>
                  <CardDescription>
                    {sectionDetail?.description}
                  </CardDescription>
                </div>
                {sectionDetail && (
                  <Badge variant="outline" className="shrink-0">
                    {categoryFor(sectionDetail.slug)}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {detailLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
              ) : (sectionDetail?.articles ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No articles in this section yet.
                </p>
              ) : (
                (sectionDetail?.articles ?? []).map((article: HelpArticle) => (
                  <ArticleCard
                    key={article.id}
                    article={article}
                    sectionSlug={sectionDetail?.slug ?? effectiveSlug}
                    isOpen={articleSlug === article.slug}
                    onToggle={() => handleArticleToggle(article.slug)}
                    onNavigate={handleNavigate}
                  />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardContent className="flex items-center justify-between gap-3 p-4">
          <div>
            <p className="text-sm font-semibold">Still stuck?</p>
            <p className="text-xs text-muted-foreground">
              Our team is here to help — open a ticket and we&rsquo;ll get back
              to you within 4 business hours.
            </p>
          </div>
          <Link
            to="/support"
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Contact support
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

/* ── Inline states (replace the removed StaticFallback) ───────────────────── */

function LoadingState() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <Skeleton className="h-5 w-24" />
        </CardHeader>
        <CardContent className="space-y-2 p-0">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-none" />
          ))}
        </CardContent>
      </Card>
      <Card className="lg:col-span-3">
        <CardHeader>
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-3/4" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
        <HelpCircle className="h-10 w-10 text-muted-foreground" />
        <div>
          <p className="text-sm font-semibold">No help content available</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Your role may not have any help sections assigned, or content is
            still being authored. Contact your tenant admin or open a support
            ticket.
          </p>
        </div>
        <Link
          to="/support"
          className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Open a support ticket
        </Link>
      </CardContent>
    </Card>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <div>
          <p className="text-sm font-semibold">
            Couldn&rsquo;t load the help guide
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            The help API returned an error. Please retry — if the problem
            persists, open a support ticket.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
          <Link
            to="/support"
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Contact support
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
