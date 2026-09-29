import { useEffect, useMemo, useState } from "react";
import "./styles.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

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

type WMTeam = {
  team_name: string;
  opponent: string;
  match_date: string | null;
  match_name: string;
  win_probability: number | null;
  draw_probability: number | null;
  loss_probability: number | null;
  clean_sheet_probability: number | null;
  expected_goals_match: number | null;
  over_0_5_probability: number | null;
  over_1_5_probability: number | null;
  over_2_5_probability: number | null;
  btts_probability: number | null;
  source_count: number;
  game_id: number | null;
};

type WMPlayer = {
  player_name: string;
  team: string | null;
  opponent: string;
  match_date: string | null;
  anytime_scorer_probability: number | null;
  first_scorer_probability: number | null;
  shots_on_target_line: number | null;
  assists_probability: number | null;
  cards_probability: number | null;
  source_count: number;
  game_id: number | null;
};

type WMSortKey = "anytime" | "first_scorer" | "clean_sheet" | "xg" | "win" | "team";
type WMPlayerSortKey = "anytime" | "first_scorer" | "team" | "player";

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [authToken, setAuthToken] = useState(
    () => localStorage.getItem("fantasy-auth-token") ?? btoa(`${import.meta.env.VITE_APP_USERNAME ?? "admin"}:${import.meta.env.VITE_APP_PASSWORD ?? "change-me"}`),
  );
  const [projections, setProjections] = useState<Projection[]>([]);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [sourceCatalog, setSourceCatalog] = useState<SourceCatalogEntry[]>([]);
  const [wmTeams, setWmTeams] = useState<WMTeam[]>([]);
  const [wmPlayers, setWmPlayers] = useState<WMPlayer[]>([]);
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [activeTab, setActiveTab] = useState<"nba" | "wm">("nba");
  const [wmView, setWmView] = useState<"teams" | "players">("teams");
  const [wmTeamFilter, setWmTeamFilter] = useState("all");
  const [wmMatchFilter, setWmMatchFilter] = useState("all");
  const [wmTeamSort, setWmTeamSort] = useState<WMSortKey>("win");
  const [wmPlayerSort, setWmPlayerSort] = useState<WMPlayerSortKey>("anytime");
  const [wmPlayerTeamFilter, setWmPlayerTeamFilter] = useState("all");

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

    apiFetch("/football/wm")
      .then((response) => (response.ok ? response.json() : { teams: [], players: [] }))
      .then((data) => {
        setWmTeams(data.teams ?? []);
        setWmPlayers(data.players ?? []);
      })
      .catch(() => {
        setWmTeams([]);
        setWmPlayers([]);
      });
  };

  useEffect(() => {
    loadData();
  }, [authToken]);

  useEffect(() => {
    if (!showSources) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setShowSources(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showSources]);

  // NBA filters
  const dates = useMemo(
    () => Array.from(new Set(projections.map((p) => p.projection_date))).sort(),
    [projections],
  );
  const teams = useMemo(
    () => Array.from(new Set(projections.map((p) => p.team).filter(Boolean) as string[])).sort(),
    [projections],
  );
  const filteredProjections = useMemo(() => {
    const q = search.trim().toLowerCase();
    return projections
      .filter((p) => dateFilter === "all" || p.projection_date === dateFilter)
      .filter((p) => teamFilter === "all" || p.team === teamFilter)
      .filter((p) => p.player_name.toLowerCase().includes(q))
      .sort((a, b) => b.fantasy_points - a.fantasy_points);
  }, [dateFilter, projections, search, teamFilter]);

  // WM filter helpers
  const wmUniqueTeams = useMemo(
    () => Array.from(new Set(wmTeams.map((t) => t.team_name))).sort(),
    [wmTeams],
  );
  const wmUniqueMatches = useMemo(
    () => Array.from(new Set(wmTeams.map((t) => t.match_name).filter(Boolean))).sort(),
    [wmTeams],
  );
  const wmPlayerTeams = useMemo(
    () => Array.from(new Set(wmPlayers.map((p) => p.team).filter(Boolean) as string[])).sort(),
    [wmPlayers],
  );

  const sortedWmTeams = useMemo(() => {
    const filtered = wmTeams
      .filter((t) => wmTeamFilter === "all" || t.team_name === wmTeamFilter)
      .filter((t) => wmMatchFilter === "all" || t.match_name === wmMatchFilter);
    return [...filtered].sort((a, b) => {
      if (wmTeamSort === "win") return (b.win_probability ?? 0) - (a.win_probability ?? 0);
      if (wmTeamSort === "clean_sheet") return (b.clean_sheet_probability ?? 0) - (a.clean_sheet_probability ?? 0);
      if (wmTeamSort === "xg") return (b.expected_goals_match ?? 0) - (a.expected_goals_match ?? 0);
      if (wmTeamSort === "team") return a.team_name.localeCompare(b.team_name);
      return 0;
    });
  }, [wmTeams, wmTeamFilter, wmMatchFilter, wmTeamSort]);

  const sortedWmPlayers = useMemo(() => {
    const filtered = wmPlayers
      .filter((p) => wmPlayerTeamFilter === "all" || p.team === wmPlayerTeamFilter);
    return [...filtered].sort((a, b) => {
      if (wmPlayerSort === "anytime") return (b.anytime_scorer_probability ?? 0) - (a.anytime_scorer_probability ?? 0);
      if (wmPlayerSort === "first_scorer") return (b.first_scorer_probability ?? 0) - (a.first_scorer_probability ?? 0);
      if (wmPlayerSort === "team") return (a.team ?? "").localeCompare(b.team ?? "");
      if (wmPlayerSort === "player") return a.player_name.localeCompare(b.player_name);
      return 0;
    });
  }, [wmPlayers, wmPlayerTeamFilter, wmPlayerSort]);

  const runRefresh = async () => {
    setIsRefreshing(true);
    try {
      await apiFetch("/refresh/run", { method: "POST" });
      loadData();
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Fantasy Odds Dashboard</p>
          <h1>{activeTab === "nba" ? "NBA FanTeam Projections" : "WM 2026 — Fantasy Odds"}</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button" onClick={() => setShowSources(true)}>
            Sources {sourceCatalog.length > 0 ? `(${sourceCatalog.length})` : ""}
          </button>
          <button className="refresh-button" disabled={isRefreshing} onClick={runRefresh}>
            {isRefreshing ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="tab-bar" aria-label="Dashboard tabs">
        <button
          className={`tab-btn${activeTab === "nba" ? " tab-btn--active" : ""}`}
          onClick={() => setActiveTab("nba")}
        >
          NBA
        </button>
        <button
          className={`tab-btn${activeTab === "wm" ? " tab-btn--active" : ""}`}
          onClick={() => setActiveTab("wm")}
        >
          WM 2026
          {wmTeams.length > 0 && <span className="tab-badge">{wmTeams.length}</span>}
        </button>
      </nav>

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

      {showSources && (
        <div className="drawer-backdrop" onClick={() => setShowSources(false)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Source quality plan">
            <div className="drawer-header">
              <div className="section-heading">
                <h2>Sources</h2>
                <span>{sourceCatalog.length} evaluated</span>
              </div>
              <button className="drawer-close" onClick={() => setShowSources(false)} aria-label="Close">✕</button>
            </div>
            <div className="source-grid">
              {sourceCatalog.map((source) => (
                <article className="source-card" key={source.key}>
                  <div className="source-card-top">
                    <strong>{source.name}</strong>
                    <span>{source.status.replace(/_/g, " ")}</span>
                  </div>
                  <dl>
                    <div><dt>Coverage</dt><dd>{source.coverage}</dd></div>
                    <div><dt>Access</dt><dd>{source.access}</dd></div>
                    <div><dt>Load</dt><dd>{source.server_load}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </aside>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* NBA TAB                                                           */}
      {/* ---------------------------------------------------------------- */}
      {activeTab === "nba" && (
        <>
          <section className="toolbar" aria-label="Projection filters">
            <input
              aria-label="Search players"
              placeholder="Search player"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select aria-label="Filter date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}>
              <option value="all">All dates</option>
              {dates.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select aria-label="Filter team" value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
              <option value="all">All teams</option>
              {teams.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </section>

          <section className="table-wrap" aria-label="NBA projection table">
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
                  <tr><td className="empty-state" colSpan={15}>No projections available yet.</td></tr>
                ) : (
                  filteredProjections.map((p) => (
                    <tr key={`${p.player_id}-${p.projection_date}`}>
                      <td className="player-cell">{p.player_name}</td>
                      <td>{p.team ?? "-"}</td>
                      <td>{p.projection_date}</td>
                      <td className="strong total-cell">{formatNumber(p.fantasy_points)}</td>
                      <td>{formatNumber(p.points)}</td>
                      <td>{formatNumber(p.threes_made)}</td>
                      <td>{formatNumber(p.rebounds)}</td>
                      <td>{formatNumber(p.assists)}</td>
                      <td>{formatNumber(p.steals)}</td>
                      <td>{formatNumber(p.blocks)}</td>
                      <td>{formatNumber(p.turnovers)}</td>
                      <td>{formatPercent(p.double_double_probability)}</td>
                      <td>{formatPercent(p.triple_double_probability)}</td>
                      <td>{p.source_count}</td>
                      <td>{formatPercent(p.confidence_score)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>
        </>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* WM 2026 TAB                                                       */}
      {/* ---------------------------------------------------------------- */}
      {activeTab === "wm" && (
        <>
          {/* Sub-view toggle */}
          <div className="wm-view-toggle">
            <button
              className={`view-toggle-btn${wmView === "teams" ? " view-toggle-btn--active" : ""}`}
              onClick={() => setWmView("teams")}
            >
              Teams
            </button>
            <button
              className={`view-toggle-btn${wmView === "players" ? " view-toggle-btn--active" : ""}`}
              onClick={() => setWmView("players")}
            >
              Spieler
            </button>
          </div>

          {/* ---- Teams view ---- */}
          {wmView === "teams" && (
            <>
              <section className="toolbar" aria-label="WM team filters">
                <select
                  aria-label="Filter by team"
                  value={wmTeamFilter}
                  onChange={(e) => setWmTeamFilter(e.target.value)}
                >
                  <option value="all">Alle Teams</option>
                  {wmUniqueTeams.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <select
                  aria-label="Filter by match"
                  value={wmMatchFilter}
                  onChange={(e) => setWmMatchFilter(e.target.value)}
                >
                  <option value="all">Alle Spiele</option>
                  {wmUniqueMatches.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <select
                  aria-label="Sort teams by"
                  value={wmTeamSort}
                  onChange={(e) => setWmTeamSort(e.target.value as WMSortKey)}
                >
                  <option value="win">Sortierung: Siegwahrscheinlichkeit</option>
                  <option value="clean_sheet">Sortierung: Clean Sheet</option>
                  <option value="xg">Sortierung: Expected Goals</option>
                  <option value="team">Sortierung: Team (A–Z)</option>
                </select>
              </section>

              <section className="table-wrap" aria-label="WM team table">
                <table>
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Gegner</th>
                      <th>Datum</th>
                      <th className="highlight-col">Sieg %</th>
                      <th>Unentschieden %</th>
                      <th>Niederlage %</th>
                      <th className="highlight-col">Clean Sheet %</th>
                      <th>xG (Spiel)</th>
                      <th>Over 0.5</th>
                      <th>Over 1.5</th>
                      <th>Over 2.5</th>
                      <th>BTTS</th>
                      <th>Quellen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedWmTeams.length === 0 ? (
                      <tr>
                        <td className="empty-state" colSpan={13}>
                          Keine WM-Daten verfügbar. Klicke auf Refresh um Daten zu laden.
                        </td>
                      </tr>
                    ) : (
                      sortedWmTeams.map((team) => (
                        <tr key={`${team.team_name}-${team.game_id}`}>
                          <td className="player-cell">{team.team_name}</td>
                          <td>{team.opponent}</td>
                          <td>{team.match_date ?? "-"}</td>
                          <td className={`strong${probClass(team.win_probability, 0.5, 0.35)}`}>
                            {formatPercent(team.win_probability)}
                          </td>
                          <td>{formatPercent(team.draw_probability)}</td>
                          <td>{formatPercent(team.loss_probability)}</td>
                          <td className={`strong${probClass(team.clean_sheet_probability, 0.4, 0.25)}`}>
                            {formatPercent(team.clean_sheet_probability)}
                          </td>
                          <td>{team.expected_goals_match?.toFixed(2) ?? "-"}</td>
                          <td>{formatPercent(team.over_0_5_probability)}</td>
                          <td>{formatPercent(team.over_1_5_probability)}</td>
                          <td className={probClass(team.over_2_5_probability, 0.6, 0.45)}>
                            {formatPercent(team.over_2_5_probability)}
                          </td>
                          <td>{formatPercent(team.btts_probability)}</td>
                          <td>{team.source_count}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </section>
            </>
          )}

          {/* ---- Players view ---- */}
          {wmView === "players" && (
            <>
              <section className="toolbar" aria-label="WM player filters">
                <select
                  aria-label="Filter by team"
                  value={wmPlayerTeamFilter}
                  onChange={(e) => setWmPlayerTeamFilter(e.target.value)}
                >
                  <option value="all">Alle Teams</option>
                  {wmPlayerTeams.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <select
                  aria-label="Sort players by"
                  value={wmPlayerSort}
                  onChange={(e) => setWmPlayerSort(e.target.value as WMPlayerSortKey)}
                >
                  <option value="anytime">Sortierung: Torschütze Anytime</option>
                  <option value="first_scorer">Sortierung: Erster Torschütze</option>
                  <option value="team">Sortierung: Team</option>
                  <option value="player">Sortierung: Spieler (A–Z)</option>
                </select>
              </section>

              <section className="table-wrap" aria-label="WM player table">
                <table>
                  <thead>
                    <tr>
                      <th>Spieler</th>
                      <th>Team</th>
                      <th>Gegner</th>
                      <th>Datum</th>
                      <th className="highlight-col">Torschütze %</th>
                      <th>Erster Torschütze %</th>
                      <th>Schüsse auf Tor</th>
                      <th>Assists %</th>
                      <th>Karte %</th>
                      <th>Quellen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedWmPlayers.length === 0 ? (
                      <tr>
                        <td className="empty-state" colSpan={10}>
                          Keine WM-Spielerdaten verfügbar. Klicke auf Refresh um Daten zu laden.
                        </td>
                      </tr>
                    ) : (
                      sortedWmPlayers.map((player) => (
                        <tr key={`${player.player_name}-${player.game_id}`}>
                          <td className="player-cell">{player.player_name}</td>
                          <td>{player.team ?? "-"}</td>
                          <td>{player.opponent}</td>
                          <td>{player.match_date ?? "-"}</td>
                          <td className={`strong${probClass(player.anytime_scorer_probability, 0.35, 0.20)}`}>
                            {formatPercent(player.anytime_scorer_probability)}
                          </td>
                          <td className={probClass(player.first_scorer_probability, 0.15, 0.08)}>
                            {formatPercent(player.first_scorer_probability)}
                          </td>
                          <td>{player.shots_on_target_line?.toFixed(1) ?? "-"}</td>
                          <td>{formatPercent(player.assists_probability)}</td>
                          <td>{formatPercent(player.cards_probability)}</td>
                          <td>{player.source_count}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </section>
            </>
          )}
        </>
      )}
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

/**
 * Return a CSS class string based on probability thresholds.
 * high: green highlight, mid: yellow highlight, else: empty
 */
function probClass(value: number | null, high: number, mid: number): string {
  if (value === null) return "";
  if (value >= high) return " prob-high";
  if (value >= mid) return " prob-mid";
  return "";
}

export default App;
