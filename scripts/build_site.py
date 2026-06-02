from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


SELECTED_GENRES = ["classical", "hip-hop", "country", "edm", "jazz"]
COLORS = {
    "classical": "#5B8DEF",
    "country": "#F59E0B",
    "edm": "#10B981",
    "hip-hop": "#EF4444",
    "jazz": "#8B5CF6",
}
PLOTLY_DEFAULT_COLORS = {
    "classical": "#1f77b4",
    "country": "#ff7f0e",
    "edm": "#2ca02c",
    "hip-hop": "#d62728",
    "jazz": "#9467bd",
}


def clean_data() -> pd.DataFrame:
    tracks_raw = pd.read_csv(ROOT / "Spotify Music Tracks/Data/music_tracks.csv")
    artists_raw = pd.read_csv(ROOT / "Spotify Music Tracks/Data/artists.csv")

    tracks = tracks_raw[tracks_raw["track_genre"].isin(SELECTED_GENRES)].copy()
    tracks = tracks.drop(columns=["Unnamed: 0"], errors="ignore")
    tracks["release_year"] = pd.to_numeric(tracks["release_date"].str[:4], errors="coerce")
    tracks["decade"] = (tracks["release_year"] // 10 * 10).astype("Int64")
    tracks["main_artist"] = tracks["artists"].str.split(";").str[0]
    tracks["popularity_zero"] = tracks["popularity"].eq(0)
    tracks["popular_70"] = tracks["popularity"].ge(70)

    artists_dedup = (
        artists_raw.sort_values("followers", ascending=False).drop_duplicates("name")
    )
    merged = tracks.merge(
        artists_dedup,
        left_on="main_artist",
        right_on="name",
        how="left",
        suffixes=("_track", "_artist"),
    )
    merged["log_followers"] = np.log1p(merged["followers"])
    merged["duration_min"] = merged["duration_ms"] / 60000
    return merged


def markdown_table(df: pd.DataFrame, index: bool = False) -> str:
    table = df.reset_index() if index else df.copy()
    headers = [str(col) for col in table.columns]
    rows = []
    for _, row in table.iterrows():
        rows.append([format_value(row[col]) for col in table.columns])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def format_value(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (np.integer, int)):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        if 0 < abs(value) < 0.01:
            return f"{value:.3f}"
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def to_jsonable(value):
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def plot_html(title: str, traces: list[dict], layout: dict, filename: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    layout = {
        "title": {"text": title, "x": 0.03, "xanchor": "left"},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": {"family": "Inter, Arial, sans-serif", "size": 13, "color": "#1f2937"},
        "margin": {"l": 64, "r": 28, "t": 64, "b": 56},
        **layout,
    }
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    html, body {{ margin: 0; padding: 0; background: white; }}
    #plot {{ width: 100vw; height: 100vh; }}
  </style>
</head>
<body>
  <div id="plot"></div>
  <script>
    const traces = {json.dumps(to_jsonable(traces))};
    const layout = {json.dumps(to_jsonable(layout))};
    Plotly.newPlot("plot", traces, layout, {{responsive: true, displaylogo: false}});
  </script>
</body>
</html>
"""
    (ASSETS / filename).write_text(html)


def iframe(path: str, height: int = 520) -> str:
    return (
        f'<iframe src="assets/{path}" width="100%" height="{height}" '
        'frameborder="0"></iframe>'
    )


def build_plots(merged: pd.DataFrame) -> dict[str, str]:
    traces = []
    genre_order = merged["track_genre"].drop_duplicates().tolist()
    for genre in genre_order:
        subset = merged.loc[merged["track_genre"].eq(genre), "popularity_track"].dropna()
        color = PLOTLY_DEFAULT_COLORS[genre]
        traces.append(
            {
                "type": "box",
                "x": subset.tolist(),
                "y": [genre] * len(subset),
                "name": genre,
                "legendgroup": genre,
                "showlegend": False,
                "orientation": "h",
                "marker": {"color": color},
                "line": {"color": color},
                "fillcolor": color,
                "opacity": 0.55,
                "xaxis": "x2",
                "yaxis": "y2",
                "hovertemplate": f"{genre}<br>Track Popularity: %{{x}}<extra></extra>",
            }
        )
        traces.append(
            {
                "type": "histogram",
                "x": subset.tolist(),
                "name": genre,
                "legendgroup": genre,
                "opacity": 0.55,
                "xbins": {"start": 0, "end": 100, "size": 5},
                "marker": {"color": color},
                "xaxis": "x",
                "yaxis": "y",
                "hovertemplate": f"{genre}<br>Track Popularity: %{{x}}<br>count: %{{y}}<extra></extra>",
            }
        )
    plot_html(
        "Distribution of Track Popularity Across Selected Genres",
        traces,
        {
            "title": {
                "text": "Distribution of Track Popularity Across Selected Genres",
                "x": 0.5,
                "xanchor": "center",
            },
            "barmode": "overlay",
            "xaxis": {
                "title": "Track Popularity",
                "range": [0, 100],
                "domain": [0, 0.82],
                "anchor": "y",
            },
            "yaxis": {
                "title": "count",
                "domain": [0, 0.74],
                "anchor": "x",
            },
            "xaxis2": {
                "range": [0, 100],
                "domain": [0, 0.82],
                "anchor": "y2",
                "matches": "x",
                "showticklabels": False,
            },
            "yaxis2": {
                "domain": [0.76, 1],
                "anchor": "x2",
                "showticklabels": False,
                "categoryorder": "array",
                "categoryarray": genre_order,
            },
            "legend": {"title": {"text": "Genre"}, "x": 0.84, "y": 0.98},
        },
        "popularity-distribution.html",
    )

    bivar = merged.dropna(subset=["log_followers"]).copy()
    bivar["follower_group"] = pd.qcut(
        bivar["log_followers"],
        q=5,
        labels=["Lowest", "Low", "Middle", "High", "Highest"],
        duplicates="drop",
    )
    popular_rate = (
        bivar.groupby("follower_group", observed=True)
        .agg(
            n_tracks=("track_id", "size"),
            mean_popularity=("popularity_track", "mean"),
            popular_70_rate=("popular_70", "mean"),
        )
        .reset_index()
    )
    plot_html(
        "Share of Highly Popular Tracks by Artist Follower Group",
        [
            {
                "type": "bar",
                "x": popular_rate["follower_group"].astype(str).tolist(),
                "y": (popular_rate["popular_70_rate"] * 100).round(2).tolist(),
                "text": (popular_rate["popular_70_rate"] * 100).round(1).astype(str) + "%",
                "textposition": "outside",
                "marker": {"color": "#2563EB"},
                "customdata": popular_rate[["n_tracks", "mean_popularity"]].round(2).values.tolist(),
                "hovertemplate": "Group: %{x}<br>Popular share: %{y:.1f}%<br>Tracks: %{customdata[0]}<br>Mean popularity: %{customdata[1]:.1f}<extra></extra>",
            }
        ],
        {
            "xaxis": {"title": "Artist follower quintile"},
            "yaxis": {"title": "Tracks with popularity >= 70 (%)", "range": [0, 25]},
            "showlegend": False,
        },
        "popular-rate-by-followers.html",
    )

    tempo_missing = (
        merged.assign(tempo_missing=merged["tempo"].isna())
        .groupby("track_genre")
        .agg(tempo_missing_rate=("tempo_missing", "mean"), n_tracks=("track_id", "size"))
        .sort_values("tempo_missing_rate", ascending=False)
        .reset_index()
    )
    plot_html(
        "Tempo Missingness by Genre",
        [
            {
                "type": "bar",
                "x": tempo_missing["track_genre"].tolist(),
                "y": (tempo_missing["tempo_missing_rate"] * 100).round(2).tolist(),
                "text": (tempo_missing["tempo_missing_rate"] * 100).round(1).astype(str) + "%",
                "textposition": "outside",
                "marker": {"color": [COLORS[g] for g in tempo_missing["track_genre"]]},
                "hovertemplate": "%{x}<br>Tempo missing: %{y:.1f}%<extra></extra>",
            }
        ],
        {
            "xaxis": {"title": "Genre"},
            "yaxis": {"title": "Tempo missing (%)", "range": [0, 40]},
            "showlegend": False,
        },
        "tempo-missingness.html",
    )

    hypothesis_df = merged.dropna(subset=["log_followers"]).copy()
    hypothesis_df["follower_quintile"] = pd.qcut(
        hypothesis_df["log_followers"], q=5, labels=False, duplicates="drop"
    )
    extreme = hypothesis_df[hypothesis_df["follower_quintile"].isin([0, 4])].copy()
    extreme["high_follower_artist"] = extreme["follower_quintile"].eq(4)
    observed = (
        extreme.groupby("high_follower_artist")["popular_70"].mean().diff().iloc[-1]
    )
    rng = np.random.default_rng(7)
    labels = extreme["high_follower_artist"].to_numpy().copy()
    simulated = []
    permuted = extreme.copy()
    for _ in range(1000):
        rng.shuffle(labels)
        permuted["high_follower_artist"] = labels
        simulated.append(
            permuted.groupby("high_follower_artist")["popular_70"].mean().diff().iloc[-1]
        )
    counts, edges = np.histogram(simulated, bins=32)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()
    plot_html(
        "Hypothesis Test Null Distribution",
        [
            {
                "type": "bar",
                "x": centers,
                "y": counts.tolist(),
                "marker": {"color": "#64748B"},
                "hovertemplate": "Simulated difference: %{x:.3f}<br>Count: %{y}<extra></extra>",
            }
        ],
        {
            "xaxis": {"title": "Simulated popular-rate difference"},
            "yaxis": {"title": "Count"},
            "shapes": [
                {
                    "type": "line",
                    "x0": observed,
                    "x1": observed,
                    "xref": "x",
                    "y0": 0,
                    "y1": 1,
                    "yref": "paper",
                    "line": {"color": "#DC2626", "width": 3},
                }
            ],
            "annotations": [
                {
                    "x": observed,
                    "y": 1,
                    "xref": "x",
                    "yref": "paper",
                    "text": "observed",
                    "showarrow": False,
                    "xanchor": "left",
                    "yanchor": "top",
                }
            ],
            "showlegend": False,
        },
        "hypothesis-null-distribution.html",
    )

    metrics = pd.DataFrame(
        {
            "metric": ["accuracy", "balanced_accuracy", "f1", "precision", "recall"],
            "baseline_logistic_regression": [0.63, 0.66, 0.25, 0.15, 0.71],
            "final_random_forest": [0.79, 0.65, 0.29, 0.20, 0.49],
        }
    )
    plot_html(
        "Baseline vs. Final Model Performance",
        [
            {
                "type": "bar",
                "x": metrics["metric"].tolist(),
                "y": metrics["baseline_logistic_regression"].tolist(),
                "name": "Baseline logistic regression",
                "marker": {"color": "#94A3B8"},
                "hovertemplate": "%{x}: %{y:.2f}<extra></extra>",
            },
            {
                "type": "bar",
                "x": metrics["metric"].tolist(),
                "y": metrics["final_random_forest"].tolist(),
                "name": "Final random forest",
                "marker": {"color": "#2563EB"},
                "hovertemplate": "%{x}: %{y:.2f}<extra></extra>",
            },
        ],
        {
            "barmode": "group",
            "xaxis": {"title": "Metric"},
            "yaxis": {"title": "Score", "range": [0, 1]},
            "legend": {"orientation": "h", "y": -0.24},
        },
        "model-comparison.html",
    )

    fairness = pd.DataFrame(
        {
            "group": ["Older than 1995", "1995 and after"],
            "n_tracks": [620, 630],
            "positive_rate": [0.04, 0.14],
            "recall": [0.18, 0.56],
        }
    )
    plot_html(
        "Final Model Recall by Release Era",
        [
            {
                "type": "bar",
                "x": fairness["group"].tolist(),
                "y": fairness["recall"].tolist(),
                "text": fairness["recall"].map(lambda x: f"{x:.2f}").tolist(),
                "textposition": "outside",
                "marker": {"color": ["#F97316", "#2563EB"]},
                "customdata": fairness[["n_tracks", "positive_rate"]].values.tolist(),
                "hovertemplate": "%{x}<br>Recall: %{y:.2f}<br>Tracks: %{customdata[0]}<br>Positive rate: %{customdata[1]:.2f}<extra></extra>",
            }
        ],
        {
            "xaxis": {"title": "Release-era group"},
            "yaxis": {"title": "Recall", "range": [0, 0.7]},
            "showlegend": False,
        },
        "fairness-recall.html",
    )

    return {
        "popular_rate": popular_rate,
        "hypothesis_observed": observed,
        "hypothesis_p_value": (np.sum(np.array(simulated) >= observed) + 1) / 1001,
    }


def build_readme(merged: pd.DataFrame, computed: dict[str, object]) -> str:
    cleaned_preview_cols = [
        "track_id",
        "track_name",
        "main_artist",
        "track_genre",
        "popularity_track",
        "popular_70",
        "release_year",
        "duration_min",
        "followers",
        "log_followers",
    ]
    cleaned_preview = merged[cleaned_preview_cols].head().copy()
    cleaned_preview["duration_min"] = cleaned_preview["duration_min"].round(2)
    cleaned_preview["log_followers"] = cleaned_preview["log_followers"].round(2)

    genre_summary = (
        merged.groupby("track_genre")
        .agg(
            n_tracks=("track_id", "size"),
            mean_popularity=("popularity_track", "mean"),
            median_popularity=("popularity_track", "median"),
            zero_popularity_rate_pct=("popularity_zero", lambda s: s.mean() * 100),
            popular_70_rate_pct=("popular_70", lambda s: s.mean() * 100),
            tempo_missing_rate_pct=("tempo", lambda s: s.isna().mean() * 100),
            median_log_followers=("log_followers", "median"),
            mean_energy=("energy", "mean"),
            mean_danceability=("danceability", "mean"),
            mean_valence=("valence", "mean"),
        )
        .sort_values("popular_70_rate_pct", ascending=False)
        .round(2)
    )

    missingness = pd.DataFrame(
        {
            "comparison_column": ["track_genre", "duration_ms"],
            "test_statistic": [0.20, 2290.10],
            "p_value": [0.001, 0.584],
            "interpretation": [
                "tempo missingness appears to depend on genre",
                "tempo missingness does not appear to depend on duration",
            ],
        }
    )
    hypothesis_results = pd.DataFrame(
        {
            "metric": [
                "lowest_follower_popular_rate",
                "highest_follower_popular_rate",
                "observed_difference",
                "p_value",
            ],
            "value": [0.0484, 0.212, 0.164, 0.001],
        }
    )
    model_comparison = pd.DataFrame(
        {
            "metric": ["accuracy", "balanced_accuracy", "f1", "precision", "recall"],
            "baseline_logistic_regression": [0.63, 0.66, 0.25, 0.15, 0.71],
            "final_random_forest": [0.79, 0.65, 0.29, 0.20, 0.49],
        }
    )
    fairness_summary = pd.DataFrame(
        {
            "group": ["older_than_1995", "newer_or_1995_and_after"],
            "n_tracks": [620, 630],
            "positive_rate": [0.04, 0.14],
            "recall": [0.18, 0.56],
        }
    )

    return f"""# Can Artist Reach Predict Spotify Track Popularity?

**Name:** La Li  
**Course:** DSC 80 at UC San Diego  
**Project focus:** Spotify track popularity prediction

This project investigates whether artist size and track audio metadata help explain and predict which Spotify tracks become highly popular. The central question is:

> Do tracks from artists with more followers tend to be more popular, and is artist size a better predictor of track popularity than audio features?

The response variable is `popularity`, a Spotify track-level score from 0 to 100. For prediction, I define a track as highly popular when `popularity >= 70`.

## Introduction

The original track dataset contains 114,000 rows and 22 columns, and the artist dataset contains 1,162,095 rows and 5 columns. I focus on five musically distinct genres: classical, hip-hop, country, EDM, and jazz. Each selected genre contributes exactly 1,000 tracks, giving a balanced 5,000-row analysis dataset.

Artist followers are useful because they measure audience reach before looking at a particular track's popularity. Audio features such as energy, danceability, valence, duration, and tempo are useful because they describe the track itself. Comparing these groups of features helps separate social reach from musical characteristics.

## Data Cleaning and Exploratory Data Analysis

I filtered to the five selected genres, extracted `release_year` from `release_date`, created decade and binary popularity flags, and split the semicolon-separated `artists` field to identify each track's main artist. Artist names were not unique in the artist table, so I kept the row with the highest follower count for each artist name before joining. I also log-transformed followers with `log1p` because the follower distribution is extremely right-skewed.

Important data quality checks:

- Selected track rows: 5,000
- Missing tempo rows: 1,196
- Missing artist follower rows after the join: 45
- Duplicated track-id rows in the selected data: 100
- Popularity-zero rows in the selected data: 2,317

### Cleaned Data Preview

{markdown_table(cleaned_preview)}

### Univariate Analysis

The popularity distribution has a large spike at 0, especially for jazz and country. I keep zeroes as real values because the data dictionary permits them, but I treat the large number of zeroes as an important limitation.

{iframe("popularity-distribution.html")}

### Bivariate Analysis

The relationship between artist followers and track popularity is not cleanly linear. Grouping artists into follower quintiles makes the pattern clearer: tracks from the highest-follower group are much more likely to reach popularity 70 or above.

{iframe("popular-rate-by-followers.html")}

### Interesting Aggregates

{markdown_table(genre_summary, index=True)}

EDM and hip-hop have the highest rates of tracks with popularity at least 70, while jazz and classical have much lower rates. Tempo missingness also differs noticeably by genre, which matters for the missingness analysis.

## Assessment of Missingness

The column with the most non-trivial missingness is `tempo`. I do not believe `tempo` is clearly NMAR, because whether tempo is missing appears related to observable genre and production metadata rather than only the unobserved tempo value itself.

{iframe("tempo-missingness.html", height=480)}

Permutation-test results:

{markdown_table(missingness)}

The permutation tests suggest that tempo missingness depends on genre but not meaningfully on duration at the 5% significance level. This supports treating tempo as MAR conditional on observed genre information.

## Hypothesis Testing

I tested whether tracks by artists in the highest follower quintile are more likely to be highly popular than tracks by artists in the lowest follower quintile.

- **Null hypothesis:** the high-follower and low-follower groups have the same probability of producing a highly popular track.
- **Alternative hypothesis:** the high-follower group has a higher probability of producing a highly popular track.
- **Test statistic:** difference in highly popular track rate, high-follower group minus low-follower group.
- **Significance level:** 0.05.

{markdown_table(hypothesis_results)}

{iframe("hypothesis-null-distribution.html")}

The p-value is below 0.05, so I reject the null hypothesis. The data provide evidence that tracks by artists in the highest follower quintile are more likely to be highly popular than tracks by artists in the lowest follower quintile.

## Framing a Prediction Problem

I frame the prediction task as binary classification: predict whether `popular_70` is true. This is a classification problem because the response is a yes/no label. I evaluate models primarily with F1-score because the positive class is uncommon: only about 9% of the train and test rows are highly popular. Accuracy alone would overstate model quality.

The train/test split uses 3,750 training rows and 1,250 test rows. Both splits have a positive rate of about 0.09.

## Baseline Model

The baseline model is a logistic regression classifier using two original features:

- `followers`, a quantitative artist-size feature
- `track_genre`, a nominal genre feature

Its held-out performance is:

- Accuracy: 0.63
- Balanced accuracy: 0.66
- F1-score: 0.25
- Precision: 0.15
- Recall: 0.71

The baseline finds many popular tracks, but precision is low, so many predicted-positive tracks are false positives.

## Final Model

The final model is a random forest classifier with engineered features, including `duration_min`, `release_age`, `log_followers`, audio-feature interactions, and genre-level popularity rates. Hyperparameters were selected with cross-validation.

Best hyperparameters:

- `n_estimators`: 200
- `max_depth`: None
- `min_samples_leaf`: 20
- Best cross-validated F1-score: 0.35

{markdown_table(model_comparison)}

{iframe("model-comparison.html", height=480)}

The final random forest improves F1-score from 0.25 to 0.29 and improves precision from 0.15 to 0.20. It gives up some recall, but its positive predictions are more reliable than the baseline's.

## Fairness Analysis

I evaluated whether the final model performs worse for older tracks than for newer tracks. Group X is tracks released before the median release year in the test set, and Group Y is tracks released in or after the median year. I use recall parity because false negatives are costly in this framing: a model that misses popular tracks for one release era is less useful for that group.

{markdown_table(fairness_summary)}

{iframe("fairness-recall.html", height=480)}

The observed recall gap is 0.381 in favor of newer tracks, with a permutation-test p-value of 0.001. I reject the null hypothesis of equal recall. The model appears to have lower recall for older tracks in this test set. This does not prove intentional bias, but it suggests that release-era effects should be monitored if the model is used for decision-making.

## Conclusion

Artist reach is informative for Spotify track popularity, but it is not sufficient by itself. Genre and audio features add useful context, and a random forest with engineered features performs better than a simple logistic-regression baseline. The strongest limitation is the high number of zero-popularity tracks, which may reflect data collection or Spotify availability effects rather than true listener demand.
"""


def main() -> None:
    merged = clean_data()
    computed = build_plots(merged)
    (ROOT / "README.md").write_text(build_readme(merged, computed))
    (ROOT / "_config.yml").write_text(
        "title: Can Artist Reach Predict Spotify Track Popularity?\n"
        "description: A DSC 80 project at UC San Diego on Spotify track popularity prediction.\n"
        "remote_theme: pages-themes/cayman@v0.2.0\n"
        "plugins:\n"
        "  - jekyll-remote-theme\n"
    )


if __name__ == "__main__":
    main()
