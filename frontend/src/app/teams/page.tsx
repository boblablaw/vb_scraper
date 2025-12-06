import Link from "next/link";
import { fetchTeams } from "@/lib/api";
import { getTeamLogoSrc } from "@/lib/logos";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type TeamsPageProps = {
  searchParams?: {
    q?: string;
    conference?: string;
    state?: string;
    tier?: string;
    page?: string;
  };
};

const PAGE_SIZE = 60;

const buildQuery = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
};

export default async function TeamsPage({ searchParams }: TeamsPageProps) {
  const q = searchParams?.q ?? "";
  const conference = searchParams?.conference ?? "";
  const state = searchParams?.state ?? "";
  const tier = searchParams?.tier ?? "";
  const page = Math.max(1, Number(searchParams?.page ?? "1"));
  const offset = (page - 1) * PAGE_SIZE;

  const data = await fetchTeams({
    search: q,
    conference,
    state,
    tier,
    limit: PAGE_SIZE,
    offset,
  });
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="teams-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Browse programs</p>
          <h1>Teams directory</h1>
          <p className="subtitle">
            Filter by name, conference, geography, or vb_scraper tier.
          </p>
        </div>
        <div className="stats-chip">
          <span>{data.total}</span> teams tracked
        </div>
      </div>

      <form className="filters" method="get">
        <input
          type="text"
          name="q"
          placeholder="Search team name..."
          defaultValue={q}
        />
        <input
          type="text"
          name="conference"
          placeholder="Conference"
          defaultValue={conference}
        />
        <input
          type="text"
          name="state"
          placeholder="State (e.g. CA)"
          defaultValue={state}
        />
        <input
          type="text"
          name="tier"
          placeholder="Tier"
          defaultValue={tier}
        />
        <button type="submit" className="btn btn-primary">
          Apply
        </button>
        <Link href="/teams" className="btn">
          Reset
        </Link>
      </form>

      <div className="card-grid">
        {data.results.map((team) => {
          const logoSrc = getTeamLogoSrc(team);
          return (
            <Link key={team.id} href={`/teams/${team.id}`} className="card">
              <div className="card-header">
                {logoSrc && (
                  <div className="card-logo">
                    <img
                      src={logoSrc}
                      alt={team.short_name ?? team.name}
                      width={40}
                      height={40}
                      loading="lazy"
                    />
                  </div>
                )}
                <div>
                  <p className="card-name">{team.short_name ?? team.name}</p>
                  <p className="card-meta">
                    {team.conference?.name ?? "Independent"}
                  </p>
                  <p className="card-meta subtle">
                    {team.city ?? "—"}, {team.state ?? "US"} · Tier{" "}
                    {team.tier ?? "—"}
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="pagination">
        <span>
          Page {page} of {totalPages}
        </span>
        <div className="pagination-actions">
          <Link
            aria-disabled={page <= 1}
            className={`btn ${page <= 1 ? "disabled" : ""}`}
            href={`/teams${buildQuery({
              q,
              conference,
              state,
              tier,
              page: Math.max(1, page - 1),
            })}`}
          >
            ← Prev
          </Link>
          <Link
            aria-disabled={page >= totalPages}
            className={`btn ${page >= totalPages ? "disabled" : ""}`}
            href={`/teams${buildQuery({
              q,
              conference,
              state,
              tier,
              page: Math.min(totalPages, page + 1),
            })}`}
          >
            Next →
          </Link>
        </div>
      </div>
    </div>
  );
}
