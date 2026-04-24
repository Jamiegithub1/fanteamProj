import { type FormEvent, useEffect, useMemo, useState } from "react";
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

type SourceCatalogEntry = {
  key: string;
  name: string;
  role: string;
  status: string;
  cost: string;
  access: string;
  coverage: string;
  server_load: string;
  reliability_notes: string;
  implementation_notes: string;
  priority: number;
};

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [authToken, setAuthToken] = useState(() => localStorage.getItem("fantasy-auth-token") ?? "");
  const [loginError, setLoginError] = useState("");
  const [projections, setProjections] = useState<Projection[]>([]);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [sourceCatalog, setSourceCatalog] = useState<SourceCatalogEntry[]>([]);
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const apiFetch = (path: string, init: RequestInit = {}) =>
    fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...(init.headers ?? {}),
        ...(authToken ? { Authorization: `Basic ${authToken}` } : {}),
      },
    });

  const loadData = () => {
    fetch(`${apiBaseUrl}/health`)
      .then((response) => setApiStatus(response.ok ? "online" : "offline"))
      .catch(() => setApiStatus("offline"));

    if (!authToken) {
      return;
    }

    apiFetch("/projections")
      .then((response) => (response.ok ? response.json() : []))
      .then(setProjections)
      .catch(() => setProjections([]));

    apiFetch("/sources/health")
      .then((response) => (response.ok ? response.json() : []))
      .then(setSourceHealth)
      .catch(() => setSourceHealth([]));

    apiFetch("/sources/catalog")
      .then((response) => (response.ok ? response.json() : []))
      .then(setSourceCatalog)
      .catch(() => setSourceCatalog([]));
  };

  useEffect(() => {
    loadData();
  }, [authToken]);

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
      await apiFetch("/refresh/run", { method: "POST" });
      loadData();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username") ?? "");
    const password = String(form.get("password") ?? "");
    const token = btoa(`${username}:${password}`);
    setLoginError("");
    const response = await fetch(`${apiBaseUrl}/auth/check`, {
      headers: { Authorization: `Basic ${token}` },
    });
    if (!response.ok) {
      setLoginError("Login failed");
      return;
    }
    localStorage.setItem("fantasy-auth-token", token);
    setAuthToken(token);
  };

  const logout = () => {
    localStorage.removeItem("fantasy-auth-token");
    setAuthToken("");
    setProjections([]);
    setSourceHealth([]);
  };

  if (!authToken) {
    return (
      <main className="login-shell">
        <form className="login-panel" onSubmit={handleLogin}>
          <p className="eyebrow">NBA Fantasy Odds</p>
          <h1>Login</h1>
          <input aria-label="Username" name="username" placeholder="Username" autoComplete="username" />
          <input
            aria-label="Password"
            name="password"
            placeholder="Password"
            type="password"
            autoComplete="current-password"
          />
          <button className="refresh-button" type="submit">
            Sign in
          </button>
          {loginError ? <p className="login-error">{loginError}</p> : null}
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">NBA Fantasy Odds</p>
          <h1>FanTeam Projections</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button" onClick={logout}>
            Logout
          </button>
          <button className="refresh-button" disabled={isRefreshing} onClick={runRefresh}>
            {isRefreshing ? "Refreshing" : "Refresh"}
          </button>
        </div>
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

      <section className="source-panel" aria-label="Source quality plan">
        <div className="section-heading">
          <h2>Sources</h2>
          <span>{sourceCatalog.length} evaluated</span>
        </div>
        <div className="source-grid">
          {sourceCatalog.map((source) => (
            <article className="source-card" key={source.key}>
              <div className="source-card-top">
                <strong>{source.name}</strong>
                <span>{source.status.replace(/_/g, " ")}</span>
              </div>
              <dl>
                <div>
                  <dt>Coverage</dt>
                  <dd>{source.coverage}</dd>
                </div>
                <div>
                  <dt>Access</dt>
                  <dd>{source.access}</dd>
                </div>
                <div>
                  <dt>Load</dt>
                  <dd>{source.server_load}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="table-wrap" aria-label="Projection table">
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
              <th>Date</th>
              <th>Total Proj</th>
              <th>Points</th>
              <th>3PM</th>
              <th>Rebounds</th>
              <th>Assists</th>
              <th>Steals</th>
              <th>Blocks</th>
              <th>Turnovers</th>
              <th>Double-Double</th>
              <th>Triple-Double</th>
              <th>Sources</th>
              <th>Confidence</th>
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
                  <td className="strong total-cell">{formatNumber(projection.fantasy_points)}</td>
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
