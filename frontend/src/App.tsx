import { useEffect, useMemo, useState } from "react";
import "./styles.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ApiStatus = "checking" | "online" | "offline";

type Projection = {
  player_id: number;
  player_name: string;
  team: string | null;
  projection_date: string;
  points: number | null;
  threes_made: number | null;
  rebounds: number | null;
  assists: number | null;
  steals: number | null;
  blocks: number | null;
  turnovers: number | null;
  double_double_probability: number | null;
  triple_double_probability: number | null;
  fantasy_points: number;
  confidence_score: number | null;
  source_count: number;
  calculated_at: string;
};

type SourceHealth = {
  source: string;
  name: string;
  status: string;
  consecutive_failures: number;
  disabled_reason: string | null;
  latency_ms: number | null;
};

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [projections, setProjections] = useState<Projection[]>([]);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = () => {
    fetch(`${apiBaseUrl}/health`)
      .then((response) => setApiStatus(response.ok ? "online" : "offline"))
      .catch(() => setApiStatus("offline"));

    fetch(`${apiBaseUrl}/projections`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setProjections)
      .catch(() => setProjections([]));

    fetch(`${apiBaseUrl}/sources/health`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setSourceHealth)
      .catch(() => setSourceHealth([]));
  };

  useEffect(() => {
    loadData();
  }, []);

  const dates = useMemo(
    () => Array.from(new Set(projections.map((projection) => projection.projection_date))).sort(),
    [projections],
  );
  const teams = useMemo(
    () =>
      Array.from(new Set(projections.map((projection) => projection.team).filter(Boolean) as string[])).sort(),
    [projections],
  );

  const filteredProjections = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return projections
      .filter((projection) => dateFilter === "all" || projection.projection_date === dateFilter)
      .filter((projection) => teamFilter === "all" || projection.team === teamFilter)
      .filter((projection) => projection.player_name.toLowerCase().includes(normalizedSearch))
      .sort((a, b) => b.fantasy_points - a.fantasy_points);
  }, [dateFilter, projections, search, teamFilter]);

  const runRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetch(`${apiBaseUrl}/refresh/run`, { method: "POST" });
      loadData();
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">NBA Fantasy Odds</p>
          <h1>FanTeam Projections</h1>
        </div>
        <button className="refresh-button" disabled={isRefreshing} onClick={runRefresh}>
          {isRefreshing ? "Refreshing" : "Refresh"}
        </button>
      </header>

      <section className="health-strip" aria-label="System status">
        <StatusPill label="Backend" value={apiStatus} tone={apiStatus} />
        {sourceHealth.length === 0 ? (
          <StatusPill label="Sources" value="waiting" tone="checking" />
        ) : (
          sourceHealth.map((source) => (
            <StatusPill
              key={source.source}
              label={source.name}
              value={`${source.status}${source.latency_ms === null ? "" : ` · ${source.latency_ms}ms`}`}
              tone={source.status === "success" ? "online" : source.status === "failed" ? "offline" : "checking"}
              title={source.disabled_reason ?? undefined}
            />
          ))
        )}
      </section>

      <section className="toolbar" aria-label="Projection filters">
        <input
          aria-label="Search players"
          placeholder="Search player"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select aria-label="Filter date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)}>
          <option value="all">All dates</option>
          {dates.map((date) => (
            <option key={date} value={date}>
              {date}
            </option>
          ))}
        </select>
        <select aria-label="Filter team" value={teamFilter} onChange={(event) => setTeamFilter(event.target.value)}>
          <option value="all">All teams</option>
          {teams.map((team) => (
            <option key={team} value={team}>
              {team}
            </option>
          ))}
        </select>
      </section>

      <section className="table-wrap" aria-label="Projection table">
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
              <th>Date</th>
              <th>FP</th>
              <th>PTS</th>
              <th>3PM</th>
              <th>REB</th>
              <th>AST</th>
              <th>STL</th>
              <th>BLK</th>
              <th>TO</th>
              <th>DD</th>
              <th>TD</th>
              <th>Src</th>
              <th>Conf</th>
            </tr>
          </thead>
          <tbody>
            {filteredProjections.length === 0 ? (
              <tr>
                <td className="empty-state" colSpan={15}>
                  No projections available yet.
                </td>
              </tr>
            ) : (
              filteredProjections.map((projection) => (
                <tr key={`${projection.player_id}-${projection.projection_date}`}>
                  <td className="player-cell">{projection.player_name}</td>
                  <td>{projection.team ?? "-"}</td>
                  <td>{projection.projection_date}</td>
                  <td className="strong">{formatNumber(projection.fantasy_points)}</td>
                  <td>{formatNumber(projection.points)}</td>
                  <td>{formatNumber(projection.threes_made)}</td>
                  <td>{formatNumber(projection.rebounds)}</td>
                  <td>{formatNumber(projection.assists)}</td>
                  <td>{formatNumber(projection.steals)}</td>
                  <td>{formatNumber(projection.blocks)}</td>
                  <td>{formatNumber(projection.turnovers)}</td>
                  <td>{formatPercent(projection.double_double_probability)}</td>
                  <td>{formatPercent(projection.triple_double_probability)}</td>
                  <td>{projection.source_count}</td>
                  <td>{formatPercent(projection.confidence_score)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}

function StatusPill({
  label,
  value,
  tone,
  title,
}: {
  label: string;
  value: string;
  tone: ApiStatus;
  title?: string;
}) {
  return (
    <div className={`status-pill ${tone}`} title={title}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatNumber(value: number | null) {
  return value === null ? "-" : value.toFixed(2);
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${Math.round(value * 100)}%`;
}

export default App;
