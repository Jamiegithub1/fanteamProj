# NBA Fantasy Odds Projection System (FanTeam)
## Phase 1 – Odds-Based Projections (NBA Only)

---

## 🎯 Ziel

Baue eine lokale Web-App, die für NBA-Spieler die erwarteten FanTeam-Fantasy-Punkte berechnet – ausschließlich basierend auf Buchmacher-Odds.

Die App soll:
- automatisch Odds sammeln
- diese aggregieren
- daraus Projektionen berechnen
- in einer Web-Oberfläche anzeigen

---

## 🧠 Grundprinzip

Keine historischen Daten verwenden.

Alle Projektionen basieren ausschließlich auf:
→ aktuellen Buchmacher-Odds

Annahme:
Alle relevanten Faktoren (Verletzungen, Usage, Lineups etc.) sind bereits in den Odds enthalten.

---

## 📊 FanTeam Scoring System

| Stat | Punkte |
|------|--------|
| Point | 1 |
| 3PT Made | 0.5 |
| Rebound | 1.25 |
| Assist | 1.5 |
| Steal | 2 |
| Block | 2 |
| Turnover | -0.5 |
| Double-Double | 1.5 |
| Triple-Double | 3 |

---

## 📦 Scope Phase 1

### In Scope
- NBA only
- nächstes Spiel pro Spieler
- Odds-basierte Projektionen
- Web-App lokal
- mehrere Buchmacher
- automatisches Refresh-System
- ressourcenschonende Datenerfassung

### Out of Scope
- Lineup Optimizer
- Verletzungslogik
- historische Daten
- Advanced Modeling

---

## 🧱 System Architektur (High-Level)

### Backend
- FastAPI (Python)
- PostgreSQL
- Scraper / Datenadapter
- Scheduler (Background Jobs)

### Frontend
- React + TypeScript
- Tabellenansicht
- Filter & Sortierung

### Infrastruktur
- Docker Compose
- .env Konfiguration

---

## ⚠️ Wichtige Regel zur Datenerfassung / Scraping

Das System soll nicht unnötig viele schwere Scraper parallel oder dauerhaft laufen lassen, damit der Hetzner-Server nicht überlastet wird.

Grundregel:
- Wenn möglich zuerst stabile frei zugängliche APIs, Network-Requests oder leichte HTTP-Requests nutzen.
- Browser-Scraping mit Playwright/Selenium nur verwenden, wenn es wirklich nötig ist.
- Playzilla ist Pflichtquelle und darf priorisiert auch per Scraping umgesetzt werden, falls keine bessere Methode verfügbar ist.
- Bei allen weiteren Buchmachern muss die Serverlast ausdrücklich in die Auswahl einfließen.
- Quellen mit hoher Datenqualität, aber extrem schwerem Scraping, sollen nur genutzt werden, wenn sie stabil und ressourcenschonend umgesetzt werden können.
- Keine unnötigen parallelen Browser-Instanzen.
- Scraper sollen gecached, gethrottled und sauber beendet werden.
- Fehlerhafte oder zu schwere Quellen sollen deaktivierbar sein, ohne dass das System crasht.
- Jede Quelle soll einen Source-Health-Status haben.

Priorität bei weiteren Quellen:
1. Datenqualität
2. NBA Player Props vollständig
3. Stabilität
4. geringe Serverlast
5. kein API-Key / kostenlos
6. einfache Wartbarkeit

---

## 📍 Meilensteine

---

### ✅ M1 – Projekt Setup

**Ziel:**
Grundstruktur steht und alles läuft lokal.

**Tasks:**
- Backend (FastAPI) initialisieren
- Frontend (React) initialisieren
- Docker Compose erstellen
- PostgreSQL integrieren
- .env.example erstellen
- Basis README

**Ergebnis:**
- App startet lokal
- Frontend + Backend erreichbar

---

### ✅ M2 – Datenmodell

**Ziel:**
Saubere Datenstruktur für Odds und Projektionen

**Entities:**
- players
- teams
- games
- bookmakers
- odds_markets
- raw_odds
- aggregated_odds
- projections
- source_health
- refresh_runs

**Ergebnis:**
- DB Schema steht
- Migration funktioniert

---

### ✅ M3 – Odds Math Engine

**Ziel:**
Odds korrekt in erwartete Werte umwandeln

**Tasks:**
- American → Probability
- Decimal → Probability
- Over/Under → Expected Value Approximation
- Aggregation (Mean/Median)
- Outlier Detection
- Confidence Score

**Ergebnis:**
- reproduzierbare Berechnung
- getestete Funktionen

---

### ✅ M4 – Playzilla Integration (Pflicht)

**Ziel:**
Erste funktionierende Odds-Quelle

**Tasks:**
- API/Network analysieren
- wenn möglich leichte Network/API-Requests nutzen
- Scraper bauen, falls nötig
- bei Scraping ressourcenschonend arbeiten
- Daten extrahieren:
  - Points
  - 3PM
  - Rebounds
  - Assists
  - Steals
  - Blocks
  - Turnovers
  - Double/Triple Double
- Speicherung in DB
- Source-Health-Status speichern

**Ergebnis:**
- stabile Datenquelle
- Playzilla funktioniert zuverlässig
- Scraping überlastet den Server nicht

---

### ✅ M5 – Weitere Buchmacher

**Ziel:**
Mehrere Quellen für bessere Datenqualität

**Mögliche Quellen:**
- DraftKings
- FanDuel
- Bet365
- Pinnacle
- Oddschecker
- ESPN Bet
- BetMGM
- Caesars

**Tasks:**
- je Quelle prüfen:
  - Datenqualität
  - verfügbare NBA Player Props
  - technische Zugänglichkeit
  - Serverlast
  - Stabilität
  - Wartbarkeit
- bevorzugt leichte API-/Network-Requests verwenden
- Browser-Scraping nur verwenden, wenn es nötig und stabil ist
- je Quelle Adapter bauen
- Stabilität prüfen
- Fehlerhandling einbauen
- Quellen deaktivierbar machen
- Source-Health-Status speichern

**Wichtige Regel:**
Nicht blind möglichst viele Scraper bauen. Qualität, Stabilität und geringe Serverlast sind wichtiger als maximale Quellenanzahl.

**Ergebnis:**
- mindestens 2–3 funktionierende Quellen, wenn technisch sinnvoll
- falls weniger Quellen stabil möglich sind, sauber dokumentieren warum
- keine Quelle darf das System crashen oder dauerhaft überlasten

---

### ✅ M6 – Datenaggregation

**Ziel:**
Mehrere Quellen → ein konsistenter Wert

**Tasks:**
- Spielernamen normalisieren
- Teams matchen
- Märkte zusammenführen
- Konsens berechnen
- Quellen tracken
- Confidence je Markt berechnen
- fehlende oder schwache Märkte markieren

**Ergebnis:**
- aggregierte Märkte pro Spieler
- nachvollziehbare Quellenbasis

---

### ✅ M7 – Projection Engine

**Ziel:**
FanTeam Punkte berechnen

**Logik:**
Projection = Summe aller Stats * Scoring

**Scoring:**
- Points * 1
- 3PT Made * 0.5
- Rebounds * 1.25
- Assists * 1.5
- Steals * 2
- Blocks * 2
- Turnovers * -0.5
- Double-Double Probability/Value * 1.5
- Triple-Double Probability/Value * 3

**Besonderheit:**
- Double/Triple Double = erwarteter Wert über Wahrscheinlichkeit
- pro Spieler nur das nächste Spiel berechnen

**Ergebnis:**
- vollständige Fantasy-Projektion pro Spieler

---

### ✅ M8 – Refresh System

**Ziel:**
Automatische Datenaktualisierung

**Regeln:**
- regulär alle 30 Minuten
- vor Game Lock alle 5 Minuten
- keine unnötigen Refreshes
- keine unnötigen parallelen Scraping-Jobs
- Browser-Instanzen sauber schließen
- Caching nutzen, wo sinnvoll

**Tasks:**
- Scheduler bauen
- manueller Refresh
- Logging
- Fehler isolieren
- Source-Health aktualisieren
- Refresh-Runs speichern
- Timeouts und Retries einbauen
- Rate Limits / Throttling einbauen

**Ergebnis:**
- stabile Updates ohne Crashes
- Server wird nicht durch Scraping überlastet

---

### ✅ M9 – Web-App (Frontend)

**Ziel:**
Benutzbare Oberfläche

**Features:**
- Tabelle mit Projektionen
- Sortierung nach Punkten
- Filter:
  - Datum
  - Team
- Suche
- Anzeige:
  - Quellen
  - Confidence
  - Last Update
  - Source Health
- Refresh Button

**Ergebnis:**
- funktionale Web-App
- Nutzer sieht, wie aktuell und stabil die Daten sind

---

### ✅ M10 – Auth & Security

**Ziel:**
Zugriff schützen

**Tasks:**
- Login / Passwort
- ENV-basierte Credentials
- keine Secrets im Code
- keine API-Keys hardcoden
- .env.example aktuell halten

**Ergebnis:**
- App ist geschützt
- Secrets bleiben außerhalb des Codes

---

### ✅ M11 – Lokales Deployment

**Ziel:**
App läuft stabil auf Server

**Tasks:**
- Docker Compose finalisieren
- Ports definieren
- Zugriff lokal über Server-IP/Port oder SSH-Tunnel
- Vorbereitung für Domain später
- Ressourcenverbrauch prüfen
- Scraper-Prozesse prüfen

**Ergebnis:**
- App läuft lokal stabil auf dem Hetzner-Server
- spätere Domain/Subdomain ist vorbereitet

---

### ✅ M12 – Testing & Stabilität

**Ziel:**
System zuverlässig machen

**Tests:**
- Unit Tests
- Scraper Tests
- Projection Tests
- DB Tests
- Refresh Tests
- Frontend Build Test

**Fehleranalyse:**
- fehlende Daten
- falsche Matches
- kaputte Quellen
- Performance
- zu hohe Serverlast
- hängende Browser-Instanzen
- fehlerhafte Refresh-Runs
- Quellen, die zu häufig oder zu schwer gescraped werden

**Wiederholen bis:**
→ keine kritischen Fehler mehr

---

## 🔁 Iterationsregel

Nach jedem Meilenstein:
1. Implementieren
2. Testen
3. Fehler beheben
4. Commit
5. Weiter zum nächsten Meilenstein

Keine Rückfragen – eigenständig entscheiden.

---

## ✅ Definition of Done (Phase 1)

Projekt ist fertig, wenn:

- Web-App lokal läuft
- Login funktioniert
- NBA-Spieler angezeigt werden
- Projektionen aus Odds berechnet werden
- Playzilla integriert ist
- mindestens eine weitere Quelle integriert ist oder sauber dokumentiert wurde, warum dies nicht stabil/ressourcenschonend möglich war
- Auto-Refresh funktioniert
- manuelles Refresh funktioniert
- Scraper überlasten den Server nicht
- fehlerhafte Quellen crashen die App nicht
- Source-Health wird angezeigt
- App stabil läuft
- Code sauber strukturiert ist
- GitHub enthält saubere Commits

---

## 🚀 Danach (nicht Teil von Phase 1)

- weitere Sportarten
- Lineup Optimizer
- Injury Integration
- Value Scores
- Alerts
- Domain/Subdomain Deployment
