import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchRosterForTeam, fetchTeamDetail } from "@/lib/api";
import { DEFAULT_SEASON } from "@/lib/config";
import { formatDecimal } from "@/lib/format";
import RosterAgGrid, {
  type RosterRow,
} from "@/components/RosterAgGrid";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type TeamDetailPageProps = {
  params: { teamId: string };
};

export default async function TeamDetailPage({
  params,
}: TeamDetailPageProps) {
  const resolvedParams = await params;
  const teamId = Number(resolvedParams.teamId);
  if (Number.isNaN(teamId)) {
    notFound();
  }

  const [teamRes, rosterRes] = await Promise.all([
    fetchTeamDetail(teamId),
    fetchRosterForTeam(teamId),
  ]);
  const team = teamRes.data;
  if (!team) {
    notFound();
  }
  const roster = rosterRes.results;
  const rosterRows: RosterRow[] = roster.map((player) => {
    const statLine =
      player.stats.find((row) => row.season === DEFAULT_SEASON) ||
      player.stats[0] ||
      {};
    return {
      id: player.id,
      name: player.name,
      position: player.position ?? "",
      classYear: player.class_year ?? "",
      heightInches: player.height_inches ?? undefined,
      ...statLine,
    };
  });

  return (
    <div className="team-detail">
      <Link href="/teams" className="link back-link">
        ← Back to teams
      </Link>

      <div className="team-hero card">
        <div className="team-hero-main">
          {team.logo_filename && (
            <div className="team-logo">
              <img
                src={`/assets/logos/${team.logo_filename}`}
                alt={team.short_name ?? team.name}
                width={56}
                height={56}
                loading="lazy"
              />
            </div>
          )}
          <div>
            <p className="eyebrow">
              {team.conference?.name ?? "Independent"}
            </p>
            <h1>{team.name}</h1>
            <p className="subtitle">
              {team.city ?? "City"}, {team.state ?? "State"} · Tier{" "}
              {team.tier ?? "—"}
            </p>
          </div>
        </div>
        <div className="team-meta">
          <div>
            <p className="meta-label">Primary site</p>
            {team.url ? (
              <a href={team.url} target="_blank" rel="noreferrer">
                {team.url}
              </a>
            ) : (
              <span>—</span>
            )}
          </div>
          <div>
            <p className="meta-label">Stats page</p>
            {team.stats_url ? (
              <a href={team.stats_url} target="_blank" rel="noreferrer">
                {team.stats_url}
              </a>
            ) : (
              <span>—</span>
            )}
          </div>
          <div>
            <p className="meta-label">Nearest airport</p>
            <span>
              {team.airport_name ?? "Unknown"} ({team.airport_code ?? "—"}) ·{" "}
              {team.airport_drive_time ?? ""}
            </span>
          </div>
        </div>
      </div>

      <div className="info-grid">
        <div className="card info-card">
          <h3>Scorecard snapshot</h3>
          {team.scorecard ? (
            <ul>
              <li>
                Acceptance rate:{" "}
                {team.scorecard.adm_rate
                  ? `${(team.scorecard.adm_rate * 100).toFixed(1)}%`
                  : "—"}
              </li>
              <li>Grad rate: {formatDecimal(team.scorecard.grad_rate, 2)}</li>
              <li>
                Median earnings:{" "}
                {team.scorecard.median_earnings
                  ? `$${team.scorecard.median_earnings.toLocaleString()}`
                  : "—"}
              </li>
            </ul>
          ) : (
            <p>No federal scorecard match.</p>
          )}
        </div>
        <div className="card info-card">
          <h3>Coaching staff</h3>
          {Array.isArray(team.coaches) && team.coaches.length > 0 ? (
            <ul>
              {team.coaches.map((coach) => (
                <li key={`${coach.name}-${coach.title}`}>
                  <strong>{coach.name}</strong>
                  {coach.title ? ` — ${coach.title}` : null}
                  <br />
                  {coach.email && (
                    <>
                      <span>{coach.email}</span>
                      <br />
                    </>
                  )}
                  {coach.phone && <span>{coach.phone}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p>No coaching staff on file.</p>
          )}
        </div>
      </div>

      <section className="roster-section">
        <div className="section-heading">
          <h2>
            Roster · {roster.length} players ({DEFAULT_SEASON} season)
          </h2>
        </div>
        <RosterAgGrid rows={rosterRows} />
      </section>
    </div>
  );
}
