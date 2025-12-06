"use client";

import { useRouter, useSearchParams } from "next/navigation";
import PlayersAgGrid, {
  type PlayerGridRow,
} from "@/components/PlayersAgGrid";

type PlayersTableShellProps = {
  rows: PlayerGridRow[];
  total: number;
  season: number;
  page: number;
  pageSize: number;
  sortField?: string;
  sortDir?: "asc" | "desc";
};

export function PlayersTableShell({
  rows,
  total,
  season,
  page,
  pageSize,
  sortField,
  sortDir = "asc",
}: PlayersTableShellProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const buildUrl = (targetPage: number, nextSortField?: string, nextSortDir?: "asc" | "desc") => {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.set("season", String(season));
    params.set("page", String(targetPage));
    if (nextSortField ?? sortField) {
      params.set("sort_field", nextSortField ?? sortField!);
    }
    if (nextSortDir ?? sortDir) {
      params.set("sort_dir", nextSortDir ?? sortDir);
    }
    return `?${params.toString()}`;
  };

  const handleSortChange = (field: string, dir: "asc" | "desc") => {
    // When sort changes, reset to first page.
    const url = buildUrl(1, field, dir);
    router.push(url);
  };

  const handlePageChange = (targetPage: number) => {
    if (targetPage < 1 || targetPage > totalPages) return;
    const url = buildUrl(targetPage);
    router.push(url);
  };

  return (
    <>
      <div className="players-grid-frame">
        <PlayersAgGrid
          rows={rows}
          sortField={sortField}
          sortDir={sortDir}
          onSortChange={handleSortChange}
        />
      </div>
      <div className="pagination">
        <span>
          Page {page} of {totalPages} · Showing {rows.length} of {total} rows
        </span>
        <div className="pagination-actions">
          <button
            type="button"
            className={`btn ${page <= 1 ? "disabled" : ""}`}
            disabled={page <= 1}
            onClick={() => handlePageChange(page - 1)}
          >
            ← Prev
          </button>
          <button
            type="button"
            className={`btn ${page >= totalPages ? "disabled" : ""}`}
            disabled={page >= totalPages}
            onClick={() => handlePageChange(page + 1)}
          >
            Next →
          </button>
        </div>
      </div>
    </>
  );
}

export default PlayersTableShell;
