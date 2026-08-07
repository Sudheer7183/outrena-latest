/**
 * pagination.tsx — reusable client-side pagination control (Task 2-b finding 11).
 *
 * Exports:
 *   - <Pagination> footer component
 *   - usePagination() hook
 *   - <PaginatedTable> wrapper component
 *
 * The hook + PaginatedTable are colocated with <Pagination> in this file so
 * callers can import everything from one path. The react-refresh rule warns
 * about non-component exports in a .tsx file; we suppress it because the hook
 * is small and the colocation improves DX (one import per page).
 */
/* eslint-disable react-refresh/only-export-components */
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState, useEffect, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { NativeSelect as Select } from "@/components/ui/select";

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="flex flex-col gap-3 px-4 py-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <span>
          Showing <span className="font-medium text-foreground">{start}</span>–
          <span className="font-medium text-foreground">{end}</span> of{" "}
          <span className="font-medium text-foreground">{total}</span>
        </span>
        {onPageSizeChange && (
          <div className="flex items-center gap-1.5">
            <span>·</span>
            <span>Rows:</span>
            <Select
              value={String(pageSize)}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="h-7 w-16 text-xs"
              aria-label="Rows per page"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={String(n)}>
                  {n}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span>
          Page <span className="font-medium text-foreground">{page + 1}</span> of{" "}
          <span className="font-medium text-foreground">{totalPages}</span>
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
          disabled={page >= totalPages - 1}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

/**
 * usePagination: manages page + pageSize state, clamps `page` when `total`
 * shrinks (e.g. after a search filter), and exposes a slice helper.
 */
export function usePagination<T>({
  items,
  initialPageSize = 20,
}: {
  items: T[];
  initialPageSize?: number;
}) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    if (page > totalPages - 1) {
      setPage(Math.max(0, totalPages - 1));
    }
  }, [page, totalPages]);

  const pageItems = useMemo(
    () => items.slice(page * pageSize, (page + 1) * pageSize),
    [items, page, pageSize],
  );

  return {
    page,
    pageSize,
    total,
    totalPages,
    pageItems,
    setPage,
    setPageSize,
    /** Reset to first page (call after a filter/search change). */
    reset: () => setPage(0),
  };
}

/**
 * PaginatedTable: wraps a shadcn-style table + <Pagination> footer. The
 * caller provides `columns` (header cells) + `renderRow` (per-row body cell).
 */
export interface PaginatedTableProps<T> {
  items: T[];
  columns: ReactNode[];
  renderRow: (item: T, index: number) => ReactNode;
  pageSize?: number;
  rowKey?: (item: T, index: number) => string | number;
  className?: string;
  emptyState?: ReactNode;
  isLoading?: boolean;
  skeletonRows?: number;
}

export function PaginatedTable<T>({
  items,
  columns,
  renderRow,
  pageSize = 20,
  rowKey,
  className,
  emptyState,
  isLoading,
  skeletonRows = 5,
}: PaginatedTableProps<T>) {
  const { page, pageSize: ps, total, pageItems, setPage, setPageSize } =
    usePagination<T>({ items, initialPageSize: pageSize });

  const colCount = columns.length;
  return (
    <div className={className}>
      <table className="w-full caption-bottom text-sm">
        <thead className="[&_tr]:border-b">
          <tr className="border-b transition-colors hover:bg-muted/50">
            {columns.map((c, i) => (
              <th
                key={i}
                className="h-10 px-3 text-left align-middle font-medium text-muted-foreground"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:last-child]:border-0">
          {isLoading ? (
            Array.from({ length: skeletonRows }).map((_, r) => (
              <tr key={r} className="border-b">
                {Array.from({ length: colCount }).map((_, c) => (
                  <td key={c} className="px-3 py-3">
                    <div className="h-4 w-full animate-pulse rounded bg-muted" />
                  </td>
                ))}
              </tr>
            ))
          ) : pageItems.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="p-0">
                {emptyState ?? (
                  <div className="flex flex-col items-center justify-center gap-2 p-10 text-center text-sm text-muted-foreground">
                    No results.
                  </div>
                )}
              </td>
            </tr>
          ) : (
            pageItems.map((item, idx) => (
              <tr
                key={rowKey ? rowKey(item, idx) : idx}
                className="border-b transition-colors hover:bg-muted/50"
              >
                {renderRow(item, idx)}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {!isLoading && total > 0 && (
        <Pagination
          page={page}
          pageSize={ps}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      )}
    </div>
  );
}
