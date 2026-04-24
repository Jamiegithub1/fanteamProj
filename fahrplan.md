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
- Scraper (Playwright)
- Scheduler (Background Jobs)

### Frontend
- React + TypeScript
- Tabellenansicht
- Filter & Sortierung

### Infrastruktur
- Docker Compose
- .env Konfiguration

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
- Scraper bauen (falls nötig)
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

**Ergebnis:**
- stabile Datenquelle

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

**Tasks:**
- je Quelle Adapter bauen
- Stabilität prüfen
- Fehlerhandling einbauen

**Ergebnis:**
- mindestens 2–3 funktionierende Quellen

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

**Ergebnis:**
- aggregierte Märkte pro Spieler

---

### ✅ M7 – Projection Engine

**Ziel:**
FanTeam Punkte berechnen

**Logik:**
Projection = Summe aller Stats * Scoring

**Besonderheit:**
- Double/Triple Double = erwarteter Wert (Wahrscheinlichkeit)

**Ergebnis:**
- vollständige Fantasy-Projektion pro Spieler

---

### ✅ M8 – Refresh System

**Ziel:**
Automatische Datenaktualisierung

**Regeln:**
- alle 30 Minuten
- vor Game Lock alle 5 Minuten

**Tasks:**
- Scheduler bauen
- manueller Refresh
- Logging
- Fehler isolieren

**Ergebnis:**
- stabile Updates ohne Crashes

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
- Refresh Button

**Ergebnis:**
- funktionale Web-App

---

### ✅ M10 – Auth & Security

**Ziel:**
Zugriff schützen

**Tasks:**
- Login / Passwort
- ENV-basierte Credentials
- keine Secrets im Code

---

### ✅ M11 – Lokales Deployment

**Ziel:**
App läuft stabil auf Server

**Tasks:**
- Docker Compose finalisieren
- Ports definieren
- Zugriff lokal (IP / Tunnel)
- Vorbereitung für Domain später

---

### ✅ M12 – Testing & Stabilität

**Ziel:**
System zuverlässig machen

**Tests:**
- Unit Tests
- Scraper Tests
- Projection Tests
- DB Tests

**Fehleranalyse:**
- fehlende Daten
- falsche Matches
- kaputte Quellen
- Performance

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
- mindestens eine weitere Quelle integriert ist
- Auto-Refresh funktioniert
- manuelles Refresh funktioniert
- App stabil läuft
- Code sauber strukturiert ist

---

## 🚀 Danach (nicht Teil von Phase 1)

- weitere Sportarten
- Lineup Optimizer
- Injury Integration
- Value Scores
- Alerts
