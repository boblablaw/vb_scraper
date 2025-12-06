import Link from "next/link";

export default function TeamNotFound() {
  return (
    <div className="card">
      <h1>Team not found</h1>
      <p>
        We couldn’t load this team from the API. Double-check that the FastAPI
        backend is running (default <code>http://localhost:8000</code>) and that
        the database has been built via{" "}
        <code>python scripts/build_database.py --season 2025</code>.
      </p>
      <p>
        <Link href="/teams" className="link">
          Back to teams directory
        </Link>
      </p>
    </div>
  );
}
