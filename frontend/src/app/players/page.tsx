export const dynamic = "force-dynamic";
export const revalidate = 0;

import { DEFAULT_SEASON } from "@/lib/config";
import { fetchAllTeams, fetchPlayersPage } from "@/lib/api";
import type { PlayerStats, TeamSummary } from "@/lib/types";
import PlayersTableShell, {
  type PlayerGridRow,
} from "@/components/PlayersTableShell";

type PlayersPageProps = {
  searchParams?: {
    season?: string;
    page?: string;
    sort_field?: string;
    sort_dir?: string;
  };
};

const parseSeason = (rawSeason: string | undefined): number => {
  if (!rawSeason) return DEFAULT_SEASON;
  const n = Number(rawSeason);
  if (Number.isNaN(n)) return DEFAULT_SEASON;
  return n;
};

export default async function PlayersPage({ searchParams }: PlayersPageProps) {
  const season = parseSeason(searchParams?.season);
  const PAGE_SIZE = 500;
  const page = Math.max(1, Number(searchParams?.page ?? "1") || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const sortField = searchParams?.sort_field;
  const sortDirParam = (searchParams?.sort_dir ?? "asc").toLowerCase();
  const sortDir: "asc" | "desc" =
    sortDirParam === "desc" ? "desc" : "asc";

  const [playersResponse, teamsResponse] = await Promise.all([
    fetchPlayersPage({
      season,
      include_stats: true,
      limit: PAGE_SIZE,
      offset,
      sort_field: sortField ?? undefined,
      sort_dir: sortDir,
    }),
    fetchAllTeams(),
  ]);
  const players = playersResponse.results;

  const teamById = new Map<number, TeamSummary>();
  for (const team of teamsResponse.results) {
    teamById.set(team.id, team);
  }

  const rows: PlayerGridRow[] = players.map((player) => {
    const seasonStats: PlayerStats | undefined =
      player.stats.find((s) => s.season === season) ?? player.stats[0];

    const statLine = seasonStats ?? {};
    const teamLabel = player.team.short_name ?? player.team.name;
    const teamMeta = teamById.get(player.team.id);
    const conferenceLabel =
      teamMeta?.conference?.name ?? "Independent";

    return {
      id: player.id,
      name: player.name,
      teamLabel,
      conferenceLabel,
      position: player.position ?? "",
      classYear: player.class_year ?? "",
      heightInches: player.height_inches ?? undefined,
      ...statLine,
    };
  });

  return (
    <div className="players-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">All players</p>
          <h1>Players directory</h1>
        </div>
        <form method="get">
          <label htmlFor="season-select" className="meta-label">
            Season
          </label>
          <select
            id="season-select"
            name="season"
            defaultValue={String(season)}
            className="season-select"
          >
            <option value={DEFAULT_SEASON}>{DEFAULT_SEASON}</option>
          </select>
        </form>
      </div>

      <section className="roster-section">
        <div className="section-heading">
          <h2>
            Players · {playersResponse.total} rows ({season} season)
          </h2>
        </div>
        <PlayersTableShell
          rows={rows}
          total={playersResponse.total}
          season={season}
          page={page}
          pageSize={PAGE_SIZE}
          sortField={sortField ?? undefined}
          sortDir={sortDir}
        />
      </section>
    </div>
  );
}
