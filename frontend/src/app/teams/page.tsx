import Link from "next/link";
import { fetchConferences, fetchTeams } from "@/lib/api";
import { getTeamLogoSrc } from "@/lib/logos";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type TeamsPageProps = {
  searchParams?: {
    search?: string;
    q?: string;
    conference?: string;
    state?: string;
    tier?: string;
  };
};

export default async function TeamsPage({ searchParams }: TeamsPageProps) {
  const search = searchParams?.search ?? searchParams?.q ?? "";
  const conference = searchParams?.conference ?? "";
  const state = searchParams?.state ?? "";
  const tier = searchParams?.tier ?? "";
  const conferences = await fetchConferences();
  const pageSize = 200;
  let offset = 0;
  let allResults: Awaited<ReturnType<typeof fetchTeams>>["results"] = [];
  let total = 0;
  let first = true;

  while (true) {
    const page = await fetchTeams({
      search,
      conference,
      state,
      tier,
      limit: pageSize,
      offset,
    });
    if (first) {
      total = page.total;
      first = false;
    }
    if (!page.results.length) {
      break;
    }
    allResults = allResults.concat(page.results);
    offset += page.limit;
    if (allResults.length >= total) {
      break;
    }
  }

  const normalized = (value: string | null | undefined) =>
    (value ?? "").toString().trim().toLowerCase();

  const filteredResults = allResults.filter((team) => {
    const matchesSearch =
      !search ||
      normalized(team.name).includes(normalized(search)) ||
      normalized(team.short_name).includes(normalized(search));
    const matchesConference =
      !conference ||
      normalized(team.conference?.name) === normalized(conference);
    const matchesState =
      !state || normalized(team.state) === normalized(state);
    const matchesTier = !tier || normalized(team.tier) === normalized(tier);
    return matchesSearch && matchesConference && matchesState && matchesTier;
  });

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
          <span>{filteredResults.length}</span> teams tracked
        </div>
      </div>

      <form className="filters" method="get" action="/teams">
        <input
          type="text"
          name="search"
          placeholder="Search team name..."
          defaultValue={search}
        />
        <select name="conference" defaultValue={conference}>
          <option value="">All conferences</option>
          {conferences.map((conf) => (
            <option key={conf.id} value={conf.name}>
              {conf.name}
            </option>
          ))}
        </select>
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
        {filteredResults.map((team) => {
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

      {/* Pagination removed: show all teams on a single page */}
    </div>
  );
}
