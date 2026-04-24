import { useEffect, useState } from "react";
import "./styles.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type ApiStatus = "checking" | "online" | "offline";

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    fetch(`${apiBaseUrl}/health`)
      .then((response) => {
        setApiStatus(response.ok ? "online" : "offline");
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  return (
    <main className="app-shell">
      <section className="status-panel">
        <div>
          <p className="eyebrow">NBA Fantasy Odds</p>
          <h1>Projection Dashboard</h1>
          <p className="summary">
            Lokales Setup fuer odds-basierte FanTeam-Projektionen. Backend,
            Frontend und PostgreSQL sind fuer die naechsten Meilensteine
            verbunden.
          </p>
        </div>

        <dl className="service-grid">
          <div>
            <dt>Backend</dt>
            <dd className={apiStatus}>{apiStatus}</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd>PostgreSQL</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>Playzilla geplant</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}

export default App;
