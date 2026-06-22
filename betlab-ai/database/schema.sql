-- ===========================================================================
-- BETLAB AI - Esquema de base de datos SQLite
-- ===========================================================================
-- Estructura normalizada para almacenar fixtures, estadísticas, cuotas,
-- ratings de equipos, value bets detectadas y resultados (para ROI).
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- --- Ligas ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leagues (
    id          INTEGER PRIMARY KEY,            -- id de API-Football
    name        TEXT NOT NULL,
    country     TEXT,
    season      INTEGER
);

-- --- Equipos ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY,            -- id de API-Football
    name        TEXT NOT NULL,
    logo        TEXT
);

-- --- Fixtures (partidos) ----------------------------------------------------
CREATE TABLE IF NOT EXISTS fixtures (
    id              INTEGER PRIMARY KEY,         -- fixture id de API-Football
    league_id       INTEGER,
    season          INTEGER,
    match_date      TEXT NOT NULL,               -- ISO 8601
    status          TEXT,                        -- NS, FT, etc.
    home_team_id    INTEGER NOT NULL,
    away_team_id    INTEGER NOT NULL,
    home_goals      INTEGER,                     -- NULL si no jugado
    away_goals      INTEGER,
    neutral         INTEGER DEFAULT 0,           -- 1 si se juega en cancha neutral
    FOREIGN KEY (league_id)    REFERENCES leagues(id),
    FOREIGN KEY (home_team_id) REFERENCES teams(id),
    FOREIGN KEY (away_team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(match_date);
CREATE INDEX IF NOT EXISTS idx_fixtures_home ON fixtures(home_team_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_away ON fixtures(away_team_id);

-- --- Estadísticas por equipo y partido --------------------------------------
CREATE TABLE IF NOT EXISTS match_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER NOT NULL,
    team_id     INTEGER NOT NULL,
    is_home     INTEGER NOT NULL,                -- 1 local / 0 visitante
    goals       INTEGER,
    xg          REAL,                            -- expected goals
    possession  REAL,                            -- %
    shots       INTEGER,
    shots_on_target INTEGER,
    UNIQUE (fixture_id, team_id),
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id),
    FOREIGN KEY (team_id)    REFERENCES teams(id)
);

-- --- Lesiones ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS injuries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER,
    team_id     INTEGER NOT NULL,
    player      TEXT,
    reason      TEXT,
    captured_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- --- Histórico de cuotas (Odds Scraper) -------------------------------------
CREATE TABLE IF NOT EXISTS odds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER NOT NULL,
    bookmaker   TEXT,
    market      TEXT NOT NULL,                   -- 1X2, OU_2.5, BTTS, AH
    selection   TEXT NOT NULL,                   -- HOME/DRAW/AWAY/OVER/UNDER/YES/NO
    odd         REAL NOT NULL,
    captured_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id)
);

CREATE INDEX IF NOT EXISTS idx_odds_fixture ON odds(fixture_id);
CREATE INDEX IF NOT EXISTS idx_odds_market ON odds(market, selection);

-- --- Ratings dinámicos de equipos -------------------------------------------
CREATE TABLE IF NOT EXISTS team_ratings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         INTEGER NOT NULL,
    attack          REAL,                        -- fuerza ofensiva (relativa a 1.0)
    defense         REAL,                        -- fuerza defensiva (relativa a 1.0)
    home_advantage  REAL,
    away_performance REAL,
    form            REAL,                        -- forma reciente [0,1]
    computed_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (team_id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- --- Value Bets detectadas --------------------------------------------------
CREATE TABLE IF NOT EXISTS value_bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      INTEGER NOT NULL,
    market          TEXT NOT NULL,
    selection       TEXT NOT NULL,
    model_prob      REAL NOT NULL,               -- probabilidad del modelo
    odd             REAL NOT NULL,               -- mejor cuota de mercado
    implied_prob    REAL NOT NULL,               -- prob. implícita de la cuota
    ev              REAL NOT NULL,               -- expected value
    confidence      REAL,                        -- Score de Confianza 0-100
    tier            TEXT,                        -- Elite/Strong/Lean/No Bet
    factors_json    TEXT,                        -- desglose de los 10 factores
    stake_pct       REAL,                        -- % bankroll (Kelly frac.)
    stake_amount    REAL,                        -- stake monetario
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id)
);

CREATE INDEX IF NOT EXISTS idx_valuebets_fixture ON value_bets(fixture_id);

-- --- Apuestas registradas + resultado (para ROI) ----------------------------
CREATE TABLE IF NOT EXISTS bet_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    value_bet_id    INTEGER,
    fixture_id      INTEGER NOT NULL,
    league_id       INTEGER,
    market          TEXT NOT NULL,
    selection       TEXT NOT NULL,
    odd             REAL NOT NULL,
    model_prob      REAL,                        -- probabilidad estimada
    ev              REAL,                        -- expected value
    stake_amount    REAL NOT NULL,
    status          TEXT DEFAULT 'PENDING',      -- PENDING/WON/LOST/VOID
    profit          REAL DEFAULT 0,              -- ganancia neta
    note            TEXT,                        -- descripción (apuestas manuales)
    manual          INTEGER DEFAULT 0,           -- 1 si la cargó el usuario a mano
    placed_at       TEXT DEFAULT (datetime('now')),
    settled_at      TEXT,
    -- ON DELETE SET NULL: las value bets pendientes se recalculan/borran cada
    -- día, pero el bet_log conserva una copia de la apuesta para el ROI.
    FOREIGN KEY (value_bet_id) REFERENCES value_bets(id) ON DELETE SET NULL,
    FOREIGN KEY (fixture_id)   REFERENCES fixtures(id)
);

CREATE INDEX IF NOT EXISTS idx_betlog_status ON bet_log(status);

-- --- Ratings de ligas (League Analyzer) -------------------------------------
CREATE TABLE IF NOT EXISTS league_ratings (
    league_id            INTEGER PRIMARY KEY,
    roi                  REAL,
    yield                REAL,
    accuracy             REAL,
    ev_hist              REAL,
    bets                 INTEGER,
    tier                 TEXT,                   -- Elite/Good/Neutral/Avoid League
    confidence_multiplier REAL DEFAULT 1.0,      -- ajuste a la confianza futura
    computed_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (league_id) REFERENCES leagues(id)
);

-- --- Partidos descartados (No Bet Engine) -----------------------------------
CREATE TABLE IF NOT EXISTS no_bets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER NOT NULL,
    match       TEXT,
    reasons     TEXT,                            -- razones del descarte (texto)
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id)
);

-- --- Estado del bankroll (Bankroll Manager) ---------------------------------
CREATE TABLE IF NOT EXISTS bankroll_state (
    id               INTEGER PRIMARY KEY CHECK (id = 1),  -- fila única
    initial_bankroll REAL NOT NULL,
    current_bankroll REAL NOT NULL,
    mode             TEXT DEFAULT 'NORMAL',      -- NORMAL/REDUCED/CONSERVATION
    stake_multiplier REAL DEFAULT 1.0,
    updated_at       TEXT DEFAULT (datetime('now'))
);

-- --- Resultados de backtesting ----------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    model       TEXT NOT NULL,                   -- Poisson / Poisson+Elo / ...
    accuracy    REAL,
    roi         REAL,
    yield       REAL,
    drawdown    REAL,
    profit      REAL,
    bets        INTEGER,
    run_at      TEXT DEFAULT (datetime('now'))
);

-- --- Ajustes de la app (clave/valor): depósito/capital inicial, etc. --------
CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
