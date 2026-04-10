from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import psycopg2
import psycopg2.extras
import os

# ─── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "changeme-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Read from environment variable (set on Render dashboard)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:kunaal06@localhost:5432/cricket_db"  # local fallback
)

app = FastAPI(
    title="IPL Cricket Analytics API",
    description="Full CRUD + analytics API for IPL data with JWT authentication",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("admin123"),
    }
}

# ─── DB connection ────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ─── Pydantic Models ──────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str

class PlayerStatResponse(BaseModel):
    player_name: str
    total_runs: int
    balls_faced: int
    strike_rate: float

class BowlerStatResponse(BaseModel):
    player_name: str
    wickets: int

class TeamRunResponse(BaseModel):
    team: str
    total_runs: int

class MatchCountResponse(BaseModel):
    team: str
    matches_played: int

class PlayerOfMatchResponse(BaseModel):
    player_name: str
    awards: int

class NoteCreate(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=100)
    note: str = Field(..., min_length=1, max_length=500)

class NoteResponse(BaseModel):
    id: int
    player_name: str
    note: str
    created_at: datetime

# ─── Auth Helpers ─────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username not in USERS_DB:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# ─── Auth Routes ─────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate and receive a JWT token. Use username: admin, password: admin123"""
    user = USERS_DB.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token(
        data={"sub": form_data.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}

# ─── Analytics Endpoints ─────────────────────────────────────────────────────
@app.get("/top-players", response_model=list[PlayerStatResponse], tags=["Analytics"])
def top_players(limit: int = 10, min_balls: int = 0, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT player_name, total_runs, balls_faced,
               COALESCE(strike_rate, 0.0) AS strike_rate
        FROM ipl_player_stats
        WHERE balls_faced >= %s
        ORDER BY total_runs DESC LIMIT %s;
    """, (min_balls, limit))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/top-bowlers", response_model=list[BowlerStatResponse], tags=["Analytics"])
def top_bowlers(limit: int = 10, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT player_name, wickets FROM ipl_bowler_stats ORDER BY wickets DESC LIMIT %s;", (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/top-teams", response_model=list[TeamRunResponse], tags=["Analytics"])
def top_teams(current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT batting_team AS team, SUM(CAST(runs_total AS INT)) AS total_runs
        FROM ipl_raw WHERE runs_total ~ '^[0-9]+$'
        GROUP BY batting_team ORDER BY total_runs DESC;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/matches-per-team", response_model=list[MatchCountResponse], tags=["Analytics"])
def matches_per_team(current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT team_name AS team, COUNT(DISTINCT match_id) AS matches_played
        FROM (
            SELECT match_id, batting_team AS team_name FROM ipl_raw
            UNION
            SELECT match_id, bowling_team FROM ipl_raw
        ) t GROUP BY team_name ORDER BY matches_played DESC;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/player-of-match", response_model=list[PlayerOfMatchResponse], tags=["Analytics"])
def player_of_match_awards(limit: int = 10, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT player_of_match AS player_name, COUNT(*) AS awards
        FROM ipl_matches
        WHERE player_of_match IS NOT NULL AND player_of_match != ''
        GROUP BY player_of_match ORDER BY awards DESC LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/seasons", tags=["Analytics"])
def list_seasons(current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT season FROM ipl_raw WHERE season IS NOT NULL ORDER BY season;")
    rows = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows

@app.get("/team-wins-by-season", tags=["Analytics"])
def team_wins_by_season(season: Optional[str] = None, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if season:
        cur.execute("""
            SELECT match_won_by AS team, COUNT(*) AS wins
            FROM ipl_matches WHERE season = %s
              AND match_won_by IS NOT NULL AND match_won_by != ''
            GROUP BY match_won_by ORDER BY wins DESC;
        """, (season,))
    else:
        cur.execute("""
            SELECT match_won_by AS team, COUNT(*) AS wins
            FROM ipl_matches
            WHERE match_won_by IS NOT NULL AND match_won_by != ''
            GROUP BY match_won_by ORDER BY wins DESC;
        """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.get("/player-search", tags=["Analytics"])
def search_player(name: str, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT ps.player_name,
               ps.total_runs, ps.balls_faced,
               COALESCE(ps.strike_rate, 0.0) AS strike_rate,
               COALESCE(bs.wickets, 0) AS wickets
        FROM ipl_player_stats ps
        LEFT JOIN ipl_bowler_stats bs ON ps.player_name = bs.player_name
        WHERE ps.player_name ILIKE %s
        ORDER BY ps.total_runs DESC LIMIT 20;
    """, (f"%{name}%",))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

# ─── CRUD: Player Notes ───────────────────────────────────────────────────────
@app.on_event("startup")
def setup_notes_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_notes (
            id SERIAL PRIMARY KEY,
            player_name VARCHAR(100) NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close(); conn.close()

@app.post("/notes", response_model=NoteResponse, status_code=201, tags=["CRUD"])
def create_note(note_in: NoteCreate, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO player_notes (player_name, note)
        VALUES (%s, %s) RETURNING id, player_name, note, created_at;
    """, (note_in.player_name, note_in.note))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    return row

@app.get("/notes", response_model=list[NoteResponse], tags=["CRUD"])
def read_notes(player_name: Optional[str] = None, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if player_name:
        cur.execute("SELECT * FROM player_notes WHERE player_name ILIKE %s ORDER BY created_at DESC;", (f"%{player_name}%",))
    else:
        cur.execute("SELECT * FROM player_notes ORDER BY created_at DESC;")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

@app.put("/notes/{note_id}", response_model=NoteResponse, tags=["CRUD"])
def update_note(note_id: int, note_in: NoteCreate, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        UPDATE player_notes SET player_name=%s, note=%s
        WHERE id=%s RETURNING id, player_name, note, created_at;
    """, (note_in.player_name, note_in.note, note_id))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    return row

@app.delete("/notes/{note_id}", tags=["CRUD"])
def delete_note(note_id: int, current_user: str = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM player_notes WHERE id=%s RETURNING id;", (note_id,))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": f"Note {note_id} deleted"}