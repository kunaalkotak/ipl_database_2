"""
IPL Cricket Analytics Dashboard
Refresh strategy: Manual — IPL data is historical/static; auto-polling would be wasteful.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(
    page_title="IPL Analytics",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem; max-width: 1400px; }

[data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2130; }
[data-testid="stSidebar"] * { color: #c9d1e0 !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 0.45rem 0.75rem; border-radius: 6px;
    transition: background 0.15s; display: block; cursor: pointer;
}
[data-testid="stSidebar"] .stRadio label:hover { background: #1a1f2e; }

.page-title { font-size: 1.75rem; font-weight: 600; color: #0f1117; letter-spacing: -0.5px; margin: 0; }
.page-subtitle { font-size: 0.85rem; color: #6b7280; margin: 0 0 1.5rem 0; }

.metric-row { display: flex; gap: 1rem; margin-bottom: 1.75rem; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 180px; background: #ffffff;
    border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 1.1rem 1.25rem; position: relative; overflow: hidden;
}
.metric-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 3px; background: #0052cc; border-radius: 10px 10px 0 0;
}
.metric-card.green::before  { background: #16a34a; }
.metric-card.amber::before  { background: #d97706; }
.metric-card.red::before    { background: #dc2626; }
.metric-label { font-size: 0.72rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem; }
.metric-value { font-size: 1.5rem; font-weight: 600; color: #111827; line-height: 1.2; font-family: 'DM Mono', monospace; }
.metric-sub { font-size: 0.75rem; color: #9ca3af; margin-top: 0.2rem; }

.section-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #9ca3af; margin: 1.5rem 0 0.2rem 0; }
.section-title { font-size: 1.1rem; font-weight: 600; color: #111827; margin: 0 0 0.9rem 0; }
.thin-divider { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }

[data-testid="stDataFrame"] th {
    background: #f9fafb !important; font-size: 0.72rem !important;
    font-weight: 600 !important; text-transform: uppercase !important;
    letter-spacing: 0.06em !important; color: #374151 !important;
}
.stButton > button {
    font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important;
    font-size: 0.85rem !important; border-radius: 7px !important;
    border: 1px solid #d1d5db !important; background: #ffffff !important;
    color: #374151 !important; transition: all 0.15s !important;
}
.stButton > button:hover { background: #f9fafb !important; border-color: #9ca3af !important; }

.note-card {
    background: #f9fafb; border: 1px solid #e5e7eb;
    border-left: 3px solid #0052cc; border-radius: 0 8px 8px 0;
    padding: 0.85rem 1rem; margin-bottom: 0.65rem;
}
.note-player { font-size: 0.8rem; font-weight: 600; color: #111827; margin-bottom: 0.2rem; }
.note-text   { font-size: 0.82rem; color: #374151; line-height: 1.5; }
.note-meta   { font-size: 0.7rem; color: #9ca3af; margin-top: 0.3rem; font-family: 'DM Mono', monospace; }
.badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; background: #dbeafe; color: #1d4ed8; }
</style>
""", unsafe_allow_html=True)

# ─── API URL — reads from env variable on Render, falls back to localhost ─────
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

PLOT_LAYOUT = dict(
    font_family="DM Sans",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=36, b=0),
    title_font_size=13,
    title_font_color="#374151",
    xaxis=dict(showgrid=False, linecolor="#e5e7eb", tickfont_size=11, tickfont_color="#6b7280"),
    yaxis=dict(gridcolor="#f3f4f6", linecolor="rgba(0,0,0,0)", tickfont_size=11, tickfont_color="#6b7280"),
    legend=dict(font_size=11, bgcolor="rgba(0,0,0,0)"),
)

if "token" not in st.session_state:
    st.session_state.token = None

def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def api_get(path, params=None):
    try:
        r = requests.get(f"{API_URL}{path}", headers=auth_headers(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"API error ({r.status_code}): {r.json().get('detail', str(e))}")
        return []
    except Exception as e:
        st.error(f"Cannot reach API. ({e})")
        return []

def api_post(path, body):
    try:
        r = requests.post(f"{API_URL}{path}", headers=auth_headers(), json=body, timeout=15)
        r.raise_for_status(); return r.json()
    except Exception as e:
        st.error(f"Error: {e}"); return None

def api_put(path, body):
    try:
        r = requests.put(f"{API_URL}{path}", headers=auth_headers(), json=body, timeout=15)
        r.raise_for_status(); return r.json()
    except Exception as e:
        st.error(f"Error: {e}"); return None

def api_delete(path):
    try:
        r = requests.delete(f"{API_URL}{path}", headers=auth_headers(), timeout=15)
        r.raise_for_status(); return r.json()
    except Exception as e:
        st.error(f"Error: {e}"); return None

@st.cache_data(ttl=300)
def fetch_top_players(limit=20, min_balls=0):
    return api_get("/top-players", params={"limit": limit, "min_balls": min_balls})

@st.cache_data(ttl=300)
def fetch_top_bowlers(limit=20):
    return api_get("/top-bowlers", params={"limit": limit})

@st.cache_data(ttl=300)
def fetch_top_teams():
    return api_get("/top-teams")

@st.cache_data(ttl=300)
def fetch_matches_per_team():
    return api_get("/matches-per-team")

@st.cache_data(ttl=300)
def fetch_player_of_match():
    return api_get("/player-of-match", params={"limit": 15})

@st.cache_data(ttl=300)
def fetch_seasons():
    return api_get("/seasons")

@st.cache_data(ttl=300)
def fetch_team_wins(season=None):
    params = {"season": season} if season else {}
    return api_get("/team-wins-by-season", params=params)

def metric_card(label, value, sub="", accent=""):
    return f"""<div class="metric-card {accent}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {"<div class='metric-sub'>" + sub + "</div>" if sub else ""}
    </div>"""

def section_header(label="", title=""):
    out = ""
    if label: out += f'<div class="section-label">{label}</div>'
    if title: out += f'<div class="section-title">{title}</div>'
    return out

# ═══ LOGIN ════════════════════════════════════════════════════════════════════
if not st.session_state.token:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🏏 IPL Analytics")
        st.markdown("<p style='color:#6b7280;margin-bottom:1.5rem'>Sign in to access the dashboard</p>", unsafe_allow_html=True)
        with st.form("login_form", border=True):
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
            if submitted:
                try:
                    r = requests.post(f"{API_URL}/auth/login",
                                      data={"username": username, "password": password}, timeout=15)
                    if r.status_code == 200:
                        st.session_state.token = r.json()["access_token"]
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Default: admin / admin123")
                except Exception as e:
                    st.error(f"Cannot connect to API.\n\n`{e}`")
    st.stop()

# ═══ SIDEBAR ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:.75rem 0 1rem 0;border-bottom:1px solid #1e2130;margin-bottom:1rem">
        <div style="font-size:1rem;font-weight:600;color:#fff">🏏 IPL Analytics</div>
        <div style="font-size:0.72rem;color:#4b5563;margin-top:2px">2008 – 2024 · Ball-by-ball</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("Navigation", [
        "Overview", "Batting", "Bowling",
        "Teams & Wins", "Player Search", "Scout Notes"
    ], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#1e2130;margin:1.25rem 0'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.7rem;color:#4b5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem'>Data</div>", unsafe_allow_html=True)
    if st.button("↻  Refresh cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("<div style='font-size:0.7rem;color:#4b5563;margin-top:.35rem'>Historical data — refresh manually.</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#1e2130;margin:1.25rem 0'>", unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        st.session_state.token = None
        st.rerun()

# ═══ OVERVIEW ═════════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown('<div class="page-title">Overview</div><div class="page-subtitle">IPL 2008 – 2024 · All seasons · Ball-by-ball data</div>', unsafe_allow_html=True)
    players = fetch_top_players(limit=50, min_balls=200)
    bowlers = fetch_top_bowlers(limit=50)
    pom     = fetch_player_of_match()
    teams   = fetch_top_teams()
    top_bat  = players[0] if players else {}
    top_bowl = bowlers[0] if bowlers else {}
    top_pom  = pom[0]     if pom     else {}
    cards = '<div class="metric-row">'
    cards += metric_card("Total Teams",      len(teams) if teams else "–", "across all seasons")
    cards += metric_card("Top Run Scorer",   top_bat.get("player_name","–"),  f"{top_bat.get('total_runs',0):,} runs",  "green")
    cards += metric_card("Top Wicket Taker", top_bowl.get("player_name","–"), f"{top_bowl.get('wickets',0)} wickets",   "amber")
    cards += metric_card("Most POM Awards",  top_pom.get("player_name","–"),  f"{top_pom.get('awards',0)} awards",      "red")
    cards += '</div>'
    st.markdown(cards, unsafe_allow_html=True)
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown(section_header("Batting", "Top 10 Run Scorers"))
        if players:
            df = pd.DataFrame(players[:10])
            fig = px.bar(df, x="total_runs", y="player_name", orientation="h",
                         color="strike_rate", color_continuous_scale=["#bfdbfe","#0052cc"],
                         labels={"total_runs":"Runs","player_name":"","strike_rate":"SR"})
            fig.update_layout(**PLOT_LAYOUT, height=320, coloraxis_colorbar=dict(title="SR",thickness=10,len=0.7))
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.markdown(section_header("Awards", "Player of the Match — Top 15"))
        if pom:
            df_p = pd.DataFrame(pom)
            fig2 = px.bar(df_p, x="awards", y="player_name", orientation="h",
                          color="awards", color_continuous_scale=["#fef3c7","#d97706"],
                          labels={"awards":"Awards","player_name":""})
            fig2.update_layout(**PLOT_LAYOUT, height=320, coloraxis_showscale=False)
            fig2.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig2, use_container_width=True)
    st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)
    st.markdown(section_header("Teams", "Total Runs by Team — All Seasons"))
    if teams:
        df_t = pd.DataFrame(teams)
        fig3 = px.bar(df_t, x="team", y="total_runs", color_discrete_sequence=["#0052cc"],
                      labels={"team":"","total_runs":"Total Runs"})
        fig3.update_layout(**PLOT_LAYOUT, height=280)
        fig3.update_xaxes(tickangle=-30)
        st.plotly_chart(fig3, use_container_width=True)

# ═══ BATTING ══════════════════════════════════════════════════════════════════
elif page == "Batting":
    st.markdown('<div class="page-title">Batting Analysis</div><div class="page-subtitle">Run tallies, strike rates and scoring patterns</div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    with c1: min_balls = st.slider("Min. balls faced", 0, 1000, 100, step=50)
    with c2: top_n = st.slider("Players shown", 5, 50, 20)
    players = fetch_top_players(limit=top_n, min_balls=min_balls)
    if players:
        df = pd.DataFrame(players)
        col_a, col_b = st.columns(2, gap="medium")
        with col_a:
            st.markdown(section_header("", "Runs vs Balls Faced"))
            fig = px.scatter(df, x="balls_faced", y="total_runs", size="strike_rate",
                             hover_name="player_name", color="strike_rate",
                             color_continuous_scale=["#bfdbfe","#0052cc"],
                             labels={"balls_faced":"Balls Faced","total_runs":"Total Runs","strike_rate":"SR"})
            fig.update_layout(**PLOT_LAYOUT, height=340, coloraxis_colorbar=dict(title="SR",thickness=10,len=0.6))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.markdown(section_header("", "Strike Rate Distribution"))
            fig2 = px.histogram(df, x="strike_rate", nbins=20, color_discrete_sequence=["#0052cc"],
                                labels={"strike_rate":"Strike Rate","count":"Players"})
            fig2.update_layout(**PLOT_LAYOUT, height=340)
            fig2.update_traces(marker_line_width=0)
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)
        st.markdown(section_header("", "Full Batting Stats"))
        df_d = df.copy()
        df_d["strike_rate"] = df_d["strike_rate"].round(2)
        st.dataframe(df_d.rename(columns={"player_name":"Player","total_runs":"Runs","balls_faced":"Balls Faced","strike_rate":"Strike Rate"}),
                     use_container_width=True, hide_index=True)

# ═══ BOWLING ══════════════════════════════════════════════════════════════════
elif page == "Bowling":
    st.markdown('<div class="page-title">Bowling Analysis</div><div class="page-subtitle">Wicket tallies and strike distribution across all seasons</div>', unsafe_allow_html=True)
    c1, _ = st.columns([1, 3])
    with c1: top_n = st.slider("Bowlers shown", 5, 50, 20)
    bowlers = fetch_top_bowlers(limit=top_n)
    if bowlers:
        df = pd.DataFrame(bowlers)
        col_a, col_b = st.columns(2, gap="medium")
        with col_a:
            st.markdown(section_header("", "Top Wicket Takers"))
            fig = px.bar(df.head(15), x="wickets", y="player_name", orientation="h",
                         color="wickets", color_continuous_scale=["#fca5a5","#dc2626"],
                         labels={"wickets":"Wickets","player_name":""})
            fig.update_layout(**PLOT_LAYOUT, height=420, coloraxis_showscale=False)
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.markdown(section_header("", "Share of Wickets — Top 10"))
            fig2 = px.pie(df.head(10), names="player_name", values="wickets",
                          color_discrete_sequence=px.colors.sequential.Reds_r[:10])
            fig2.update_layout(**PLOT_LAYOUT, height=420)
            fig2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=10, hole=0.35)
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)
        st.markdown(section_header("", "Full Bowling Stats"))
        st.dataframe(df.rename(columns={"player_name":"Bowler","wickets":"Wickets"}),
                     use_container_width=True, hide_index=True)

# ═══ TEAMS & WINS ═════════════════════════════════════════════════════════════
elif page == "Teams & Wins":
    st.markdown('<div class="page-title">Teams & Wins</div><div class="page-subtitle">Win rates, matches played and run totals by franchise</div>', unsafe_allow_html=True)
    seasons = fetch_seasons()
    season_opts = ["All seasons"] + (seasons if seasons else [])
    c1, _ = st.columns([1.5, 3])
    with c1: selected = st.selectbox("Season", season_opts)
    season_param = None if selected == "All seasons" else selected
    wins_data  = fetch_team_wins(season=season_param)
    teams_data = fetch_matches_per_team()
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown(section_header("", f"Wins — {selected}"))
        if wins_data:
            df_w = pd.DataFrame(wins_data)
            fig = px.bar(df_w, x="wins", y="team", orientation="h",
                         color="wins", color_continuous_scale=["#bbf7d0","#16a34a"],
                         labels={"wins":"Wins","team":""})
            fig.update_layout(**PLOT_LAYOUT, height=400, coloraxis_showscale=False)
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No win data available for this season.")
    with col_b:
        st.markdown(section_header("", "Matches Played per Team"))
        if teams_data:
            df_m = pd.DataFrame(teams_data)
            fig2 = px.bar(df_m, x="matches_played", y="team", orientation="h",
                          color_discrete_sequence=["#0052cc"],
                          labels={"matches_played":"Matches","team":""})
            fig2.update_layout(**PLOT_LAYOUT, height=400)
            fig2.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig2, use_container_width=True)

# ═══ PLAYER SEARCH ════════════════════════════════════════════════════════════
elif page == "Player Search":
    st.markdown('<div class="page-title">Player Search</div><div class="page-subtitle">Look up any player — combined batting and bowling stats</div>', unsafe_allow_html=True)
    c1, _ = st.columns([2, 3])
    with c1:
        query = st.text_input("", placeholder="Search by name — e.g. Kohli, Bumrah, Rohit", label_visibility="collapsed")
    if query:
        results = api_get("/player-search", params={"name": query})
        if results:
            df = pd.DataFrame(results)
            df["strike_rate"] = df["strike_rate"].round(2)
            player = results[0]
            st.markdown(section_header("Top match", player["player_name"]))
            col_r, col_t = st.columns([1, 1.6], gap="medium")
            with col_r:
                cats = ["Runs", "Balls Faced", "Strike Rate", "Wickets"]
                maxv = [8000, 5000, 200, 200]
                keys = ["total_runs", "balls_faced", "strike_rate", "wickets"]
                vals = [round(min(player.get(k,0)/m*100, 100), 1) for k, m in zip(keys, maxv)]
                fig = go.Figure(go.Scatterpolar(
                    r=vals+[vals[0]], theta=cats+[cats[0]], fill="toself",
                    fillcolor="rgba(0,82,204,0.12)", line=dict(color="#0052cc", width=2),
                ))
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0,100], showticklabels=False, gridcolor="#e5e7eb"),
                        angularaxis=dict(tickfont_size=11, tickfont_color="#374151", gridcolor="#e5e7eb"),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=40,r=40,t=40,b=40),
                    height=300, font_family="DM Sans", showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            with col_t:
                st.markdown(section_header("", "All results"))
                st.dataframe(df.rename(columns={"player_name":"Player","total_runs":"Runs","balls_faced":"Balls","strike_rate":"SR","wickets":"Wickets"}),
                             use_container_width=True, hide_index=True, height=300)
        else:
            st.info(f"No players found matching **{query}**.")
    else:
        st.markdown("""<div style="padding:3rem;text-align:center;color:#9ca3af;font-size:0.9rem;
                    border:1px dashed #e5e7eb;border-radius:10px;margin-top:1rem">
                    Type a player name above to search</div>""", unsafe_allow_html=True)

# ═══ SCOUT NOTES ══════════════════════════════════════════════════════════════
elif page == "Scout Notes":
    st.markdown('<div class="page-title">Scout Notes</div><div class="page-subtitle">Create, edit and delete analyst notes for any player</div>', unsafe_allow_html=True)
    tab_view, tab_add, tab_edit, tab_delete = st.tabs(["View Notes", "Add Note", "Edit Note", "Delete Note"])
    with tab_view:
        c1, _ = st.columns([2, 3])
        with c1:
            filter_name = st.text_input("Filter by player", placeholder="Leave blank to show all", label_visibility="collapsed")
        notes = api_get("/notes", params={"player_name": filter_name} if filter_name else {})
        if notes:
            for n in notes:
                ts = n.get("created_at","")[:16].replace("T"," ")
                st.markdown(f"""<div class="note-card">
                    <div class="note-player">{n["player_name"]} &nbsp;<span class="badge">#{n["id"]}</span></div>
                    <div class="note-text">{n["note"]}</div>
                    <div class="note-meta">{ts}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="padding:2rem;text-align:center;color:#9ca3af;font-size:0.85rem;">No notes found.</div>', unsafe_allow_html=True)
    with tab_add:
        with st.form("add_note_form", border=False):
            p_name = st.text_input("Player name", placeholder="e.g. Virat Kohli")
            p_note = st.text_area("Note", placeholder="Write your scouting note here…", height=120)
            if st.form_submit_button("Save note", type="primary"):
                if p_name.strip() and p_note.strip():
                    result = api_post("/notes", {"player_name": p_name.strip(), "note": p_note.strip()})
                    if result:
                        st.success(f"Note saved — ID #{result['id']}")
                        st.cache_data.clear()
                else:
                    st.warning("Please fill in both fields.")
    with tab_edit:
        c1, _ = st.columns([1, 3])
        with c1: note_id = st.number_input("Note ID to edit", min_value=1, step=1)
        with st.form("edit_note_form", border=False):
            new_name = st.text_input("Updated player name")
            new_note = st.text_area("Updated note", height=120)
            if st.form_submit_button("Update note", type="primary"):
                if new_name.strip() and new_note.strip():
                    result = api_put(f"/notes/{note_id}", {"player_name": new_name.strip(), "note": new_note.strip()})
                    if result:
                        st.success(f"Note #{note_id} updated.")
                        st.cache_data.clear()
                else:
                    st.warning("Fill in both fields.")
    with tab_delete:
        c1, _ = st.columns([1, 3])
        with c1: del_id = st.number_input("Note ID to delete", min_value=1, step=1)
        st.warning(f"This will permanently delete note #{del_id}. This cannot be undone.")
        if st.button("Delete note", type="primary"):
            result = api_delete(f"/notes/{del_id}")
            if result:
                st.success(result.get("message", "Deleted."))
                st.cache_data.clear()