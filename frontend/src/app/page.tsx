export const dynamic = "force-dynamic";
export const revalidate = 0;

import Link from "next/link";
import { fetchTeams } from "@/lib/api";
import { getTeamLogoSrc } from "@/lib/logos";

export default async function Home() {
  const { results } = await fetchTeams({ limit: 6 });

  return (
    <div className="home">
      <section className="hero">
        <p className="eyebrow">Division I Women&apos;s Volleyball</p>
        <h1>Data explorer for every program, player, and stat line.</h1>
        <p className="subtitle">
          Powered by the vb_scraper pipeline and FastAPI backend. Browse
          programs, inspect rosters, and prepare your next scouting report.
        </p>
        <div className="hero-actions">
          <Link href="/teams" className="btn btn-primary">
            Browse teams
          </Link>
          <a
            href={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
            className="btn"
          >
            View API
          </a>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <h2>Featured schools</h2>
          <Link href="/teams" className="link">
            View directory →
          </Link>
        </div>
        <div className="card-grid">
          {results.map((team) => {
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
                      {team.conference?.name ?? "Independent"} ·{" "}
                      {team.state ?? "US"}
                    </p>
                    <p className="card-meta subtle">
                      Tier {team.tier ?? "—"} · {team.city ?? "City TBD"}
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
