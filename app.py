import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="MovieLens Dashboard", page_icon="🎬", layout="wide")

DATA_PATH = "movie_ratings.csv"
ACCENT = "#4C78A8"
HIGHLIGHT = "#F58518"


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["genres"] = df["genres"].fillna("")
    return df


def explode_genres(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (rating, genre). A movie with 3 genres appears under all 3."""
    out = df[["userId", "movieId", "rating", "genres"]].copy()
    out["genre"] = out["genres"].str.split("|")
    out = out.explode("genre")
    out["genre"] = out["genre"].str.strip()
    return out[(out["genre"] != "") & (out["genre"] != "(no genres listed)")]


try:
    raw = load_data(DATA_PATH)
except FileNotFoundError:
    st.error(f"Could not find `{DATA_PATH}`. Place it next to app.py in the repo.")
    st.stop()

# ------------------------------------------------------------ sidebar filters
all_genres = sorted(explode_genres(raw)["genre"].unique())
years = raw["year"].dropna().astype(int)
ymin, ymax = int(years.min()), int(years.max())

st.sidebar.header("Filters")
year_range = st.sidebar.slider("Movie release year", ymin, ymax, (ymin, ymax))
sel_genres = st.sidebar.multiselect("Genres", all_genres, default=all_genres)
st.sidebar.caption("Filters apply to every chart. Genre filter keeps movies "
                   "with at least one selected genre.")

df = raw
if year_range != (ymin, ymax):
    df = df[df["year"].between(year_range[0], year_range[1])]

gdf_all = explode_genres(df)
genre_filter_active = set(sel_genres) != set(all_genres)
if genre_filter_active:
    keep_ids = gdf_all.loc[gdf_all["genre"].isin(sel_genres), "movieId"].unique()
    df = df[df["movieId"].isin(keep_ids)]
    gdf_all = gdf_all[gdf_all["movieId"].isin(keep_ids)]
gdf = gdf_all[gdf_all["genre"].isin(sel_genres)]  # genres shown in Q1/Q2

if df.empty or not sel_genres:
    st.warning("No data matches the current filters. Widen the year range or pick genres.")
    st.stop()

st.title("🎬 MovieLens Ratings Dashboard")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Ratings", f"{len(df):,}")
k2.metric("Movies rated", f"{df['movieId'].nunique():,}")
k3.metric("Users", f"{df['userId'].nunique():,}")
k4.metric("Mean rating", f"{df['rating'].mean():.2f}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Genre breakdown", "Genre satisfaction", "Ratings over time", "Best movies"]
)

# ---------------------------------------------------------------- Q1
with tab1:
    st.subheader("Distribution of genres among rated movies")
    metric = st.radio("Count by", ["Unique movies", "Number of ratings"],
                      horizontal=True, key="q1_metric")
    if metric == "Unique movies":
        counts = gdf.groupby("genre")["movieId"].nunique()
        xlabel = "Unique rated movies"
    else:
        counts = gdf.groupby("genre").size()
        xlabel = "Number of ratings"
    counts = counts.sort_values().rename("count").reset_index()
    fig = px.bar(counts, x="count", y="genre", orientation="h",
                 labels={"count": xlabel, "genre": ""},
                 color_discrete_sequence=[ACCENT], text="count")
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(height=max(400, 28 * len(counts)), margin=dict(l=0, r=40, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Multi-genre movies count once under each of their genres, "
               "so totals exceed the number of movies.")

# ---------------------------------------------------------------- Q2
with tab2:
    st.subheader("Average rating by genre")
    min_n = st.slider("Minimum ratings for a genre to be shown", 1, 5000, 1, key="q2_min")
    stats = gdf.groupby("genre")["rating"].agg(mean="mean", n="size").reset_index()
    stats = stats[stats["n"] >= min_n].sort_values("mean")
    if stats.empty:
        st.warning("No genres meet that minimum.")
    else:
        lo = max(0.0, stats["mean"].min() - 0.15)
        hi = min(5.0, stats["mean"].max() + 0.15)
        extremes = {stats.iloc[0]["genre"], stats.iloc[-1]["genre"]}
        colors = [HIGHLIGHT if g in extremes else ACCENT for g in stats["genre"]]
        fig = go.Figure(go.Bar(
            x=stats["mean"], y=stats["genre"], orientation="h", marker_color=colors,
            text=stats["mean"].round(2), textposition="outside", customdata=stats["n"],
            hovertemplate="%{y}<br>Mean: %{x:.3f}<br>Ratings: %{customdata:,}<extra></extra>"))
        fig.update_xaxes(range=[lo, hi], title="Mean rating (axis zoomed, does not start at 0)")
        fig.update_layout(height=max(400, 28 * len(stats)), margin=dict(l=0, r=40, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
        best, worst = stats.iloc[-1], stats.iloc[0]
        c1, c2 = st.columns(2)
        c1.success(f"Highest: {best['genre']} ({best['mean']:.2f}, {int(best['n']):,} ratings)")
        c2.error(f"Lowest: {worst['genre']} ({worst['mean']:.2f}, {int(worst['n']):,} ratings)")

# ---------------------------------------------------------------- Q3
with tab3:
    st.subheader("Mean rating by movie release year")
    min_year_n = st.slider("Minimum ratings per release year", 1, 500, 1, key="q3_min")
    yr = (df.dropna(subset=["year"]).groupby("year")["rating"]
            .agg(mean="mean", n="size").reset_index())
    yr = yr[yr["n"] >= min_year_n]
    if yr.empty:
        st.warning("No years meet that minimum.")
    else:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Scatter(
            x=yr["year"], y=yr["mean"], mode="lines+markers", line=dict(color=ACCENT),
            hovertemplate="%{x:.0f}<br>Mean: %{y:.3f}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Bar(
            x=yr["year"], y=yr["n"], marker_color="#B0B0B0",
            hovertemplate="%{x:.0f}<br>Ratings: %{y:,}<extra></extra>"), row=2, col=1)
        fig.update_yaxes(title_text="Mean rating", row=1, col=1)
        fig.update_yaxes(title_text="# ratings", row=2, col=1)
        fig.update_xaxes(title_text="Movie release year", row=2, col=1)
        fig.update_layout(height=600, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- Q4
with tab4:
    st.subheader("Top 5 best-rated movies, with a minimum-ratings floor")
    c1, c2 = st.columns(2)
    floor_a = int(c1.number_input("Floor A (min ratings)", 1, 100000, 50, key="floor_a"))
    floor_b = int(c2.number_input("Floor B (min ratings)", 1, 100000, 150, key="floor_b"))

    movies = (df.groupby(["movieId", "title"])["rating"]
                .agg(mean="mean", n="size").reset_index())

    def top5(floor: int) -> pd.DataFrame:
        t = movies[movies["n"] >= floor].sort_values(["mean", "n"], ascending=[False, False])
        return t.head(5).reset_index(drop=True)

    ta, tb = top5(floor_a), top5(floor_b)
    only_a = set(ta["movieId"]) - set(tb["movieId"])
    only_b = set(tb["movieId"]) - set(ta["movieId"])

    def chart(t: pd.DataFrame, floor: int, unique_ids: set):
        t = t.iloc[::-1]
        colors = [HIGHLIGHT if m in unique_ids else ACCENT for m in t["movieId"]]
        fig = go.Figure(go.Bar(
            x=t["mean"], y=t["title"], orientation="h", marker_color=colors,
            text=[f"{m:.2f} ({n:,})" for m, n in zip(t["mean"], t["n"])],
            textposition="inside", customdata=t["n"],
            hovertemplate="%{y}<br>Mean: %{x:.3f}<br>Ratings: %{customdata:,}<extra></extra>"))
        fig.update_xaxes(range=[max(0.0, t["mean"].min() - 0.3), 5], title="Mean rating")
        fig.update_layout(title=f"At least {floor} ratings", height=350,
                          margin=dict(l=0, r=0, t=40, b=0))
        return fig

    left, right = st.columns(2)
    for col, t, floor, uniq in ((left, ta, floor_a, only_a), (right, tb, floor_b, only_b)):
        with col:
            if t.empty:
                st.warning(f"No movies have at least {floor} ratings.")
            else:
                st.plotly_chart(chart(t, floor, uniq), use_container_width=True)
    st.caption("Bars show mean rating (number of ratings). Orange = in only one of the two lists.")

    if not ta.empty and not tb.empty:
        rank_a = {m: i + 1 for i, m in enumerate(ta["movieId"])}
        rank_b = {m: i + 1 for i, m in enumerate(tb["movieId"])}
        ids = list(dict.fromkeys(list(ta["movieId"]) + list(tb["movieId"])))
        titles = movies.set_index("movieId")["title"]
        table = pd.DataFrame({
            "Title": [titles[i] for i in ids],
            f"Rank @ ≥{floor_a}": [rank_a.get(i, "—") for i in ids],
            f"Rank @ ≥{floor_b}": [rank_b.get(i, "—") for i in ids],
        })
        st.dataframe(table, hide_index=True, use_container_width=True)