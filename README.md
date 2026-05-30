# Can Artist Reach Predict Spotify Track Popularity?

**Name:** La Li  
**Course:** DSC 80 at UC San Diego  
**Project focus:** Spotify track popularity prediction

This project investigates whether artist size and track audio metadata help explain and predict which Spotify tracks become highly popular. The central question is:

> Do tracks from artists with more followers tend to be more popular, and is artist size a better predictor of track popularity than audio features?

The response variable is `popularity`, a Spotify track-level score from 0 to 100. For prediction, I define a track as highly popular when `popularity >= 70`.

## Introduction

The original track dataset (`music_tracks.csv`) contains 114,000 rows and 22 columns, and the artist dataset (`artists.csv`) contains 1,162,095 rows and 5 columns. I focus on five musically distinct genres: classical, hip-hop, country, EDM, and jazz. Each selected genre contributes exactly 1,000 tracks, giving a balanced 5,000-row analysis dataset.

The columns most relevant to the central question are described below:

| Column | Source | Type | Description |
| --- | --- | --- | --- |
| `popularity` | music_tracks | quantitative | Spotify score 0–100 based on total plays and recency; the response variable |
| `track_genre` | music_tracks | nominal | Genre label assigned by Spotify |
| `release_date` | music_tracks | nominal | Release date in YYYY, YYYY-MM, or YYYY-MM-DD format |
| `duration_ms` | music_tracks | quantitative | Track duration in milliseconds |
| `energy` | music_tracks | quantitative | Perceptual intensity and activity (0–1) |
| `danceability` | music_tracks | quantitative | Suitability for dancing based on tempo and rhythm (0–1) |
| `valence` | music_tracks | quantitative | Musical positiveness; high = happy, low = sad (0–1) |
| `tempo` | music_tracks | quantitative | Estimated beats per minute |
| `loudness` | music_tracks | quantitative | Overall loudness in decibels |
| `speechiness` | music_tracks | quantitative | Presence of spoken words (0–1) |
| `acousticness` | music_tracks | quantitative | Confidence the track is acoustic (0–1) |
| `instrumentalness` | music_tracks | quantitative | Probability the track contains no vocals (0–1) |
| `explicit` | music_tracks | nominal | Whether the track contains explicit content |
| `mode` | music_tracks | ordinal | Major (1) or minor (0) key |
| `followers` | artists | quantitative | Total follower count on Spotify for the main artist |
| `popularity` | artists | quantitative | Artist-level popularity score 0–100 (distinct from track popularity) |

## Data Cleaning and Exploratory Data Analysis

I filtered to the five selected genres, extracted `release_year` from `release_date`, created decade and binary popularity flags, and split the semicolon-separated `artists` field to identify each track's main artist. Artist names were not unique in the artist table, so I kept the row with the highest follower count for each artist name before joining. I also log-transformed followers with `log1p` because the follower distribution is extremely right-skewed.

Important data quality checks:

- Selected track rows: 5,000
- Missing tempo rows: 1,196
- Missing artist follower rows after the join: 45
- Duplicated track-id rows in the selected data: 100
- Popularity-zero rows in the selected data: 2,317

### Cleaned Data Preview

| track_id | track_name | main_artist | track_genre | popularity_track | popular_70 | release_year | duration_min | followers | log_followers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7wrYBASu0OoxoDErd4Edxd | Zara Zara | Bombay Jayashri | classical | 58 | 0 | 2001 | 4.97 | 124,188 | 11.73 |
| 72HdutlIHBZJ7WT1xVAAZT | Kajra Re | Shankar | classical | 59 | 0 | 2005 | 8.04 | 11,604 | 9.36 |
| 7JGgKHHDgJCJkQCQxyHHdl | Zara Zara - Lofi | Bombay Jayashri | classical | 54 | 0 | 1984 | 3.66 | 124,188 | 11.73 |
| 3YRj4jmwois2ctPnhwSwFo | Vaseegara | Bombay Jayashri | classical | 68 | 0 | 1972 | 4.99 | 124,188 | 11.73 |
| 3tp3ij9dtY3CacQgd1OvRf | Zara Zara - LoFi Chill | Bombay Jayashri | classical | 59 | 0 | 1987 | 6.46 | 124,188 | 11.73 |

### Univariate Analysis

The popularity distribution has a large spike at 0, especially for jazz and country. I keep zeroes as real values because the data dictionary permits them, but I treat the large number of zeroes as an important limitation.

<iframe src="assets/popularity-distribution.html" width="100%" height="520" frameborder="0"></iframe>

### Bivariate Analysis

The relationship between artist followers and track popularity is not cleanly linear. Grouping artists into follower quintiles makes the pattern clearer: tracks from the highest-follower group are much more likely to reach popularity 70 or above.

<iframe src="assets/popular-rate-by-followers.html" width="100%" height="520" frameborder="0"></iframe>

### Interesting Aggregates

| track_genre | n_tracks | mean_popularity | median_popularity | zero_popularity_rate_pct | popular_70_rate_pct | tempo_missing_rate_pct | median_log_followers | mean_energy | mean_danceability | mean_valence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| edm | 1000 | 35.03 | 47 | 36.2 | 18.2 | 14.1 | 14.53 | 0.76 | 0.65 | 0.47 |
| hip-hop | 1000 | 37.76 | 58 | 28.9 | 13.4 | 17.6 | 15.08 | 0.68 | 0.74 | 0.55 |
| country | 1000 | 17.03 | 0 | 58.7 | 8.7 | 21.8 | 13.71 | 0.6 | 0.56 | 0.52 |
| jazz | 1000 | 13.63 | 0 | 68.1 | 2.5 | 31.2 | 13.89 | 0.35 | 0.51 | 0.49 |
| classical | 1000 | 13.06 | 3 | 39.8 | 0.7 | 34.9 | 13.78 | 0.19 | 0.38 | 0.38 |

EDM and hip-hop have the highest rates of tracks with popularity at least 70, while jazz and classical have much lower rates. Tempo missingness also differs noticeably by genre, which matters for the missingness analysis.

## Assessment of Missingness

Two columns have non-trivial missing values in the analysis dataset: `tempo` (1,196 missing, ~24%) and `followers` (45 missing, ~0.9% after the artist join).

### NMAR Analysis

I do not believe either column is clearly **NMAR**. For `tempo`, whether it is missing appears related to observable properties such as genre and production style rather than to the unobserved tempo value itself — a track's genre is already recorded, making the missingness explainable by an observed column. For `followers`, the missingness arises because the artist name in the track table did not match any row in the artist table; this is a data-linkage limitation tied to the artist's name string, not to their actual follower count. If I had an artist identifier (such as a Spotify artist ID) instead of relying on name matching, the missingness would likely disappear entirely, further supporting a MAR classification.

### Tempo Missingness

<iframe src="assets/tempo-missingness.html" width="100%" height="480" frameborder="0"></iframe>

| comparison_column | test_statistic | p_value | interpretation |
| --- | --- | --- | --- |
| track_genre | 0.2 | 0.001 | tempo missingness depends on genre (MAR) |
| duration_ms | 2,290 | 0.58 | tempo missingness does not depend on duration |

Tempo missingness depends on genre (p < 0.05) but not meaningfully on track duration. Classical and jazz have especially high missing-tempo rates, consistent with those genres containing more free-form or non-metered recordings that Spotify's BPM algorithm cannot analyze. This supports classifying `tempo` as **MAR** conditioned on genre.

### Followers Missingness

| comparison_column | test_statistic | p_value | interpretation |
| --- | --- | --- | --- |
| track_genre | — | — | see permutation test in notebook |
| popularity_track | — | — | see permutation test in notebook |

Permutation tests show that `followers` missingness depends on `track_genre` (p < 0.05) but not on `popularity_track`. Tracks whose main artist cannot be matched in the artist table cluster in particular genres — likely genres with more niche or non-English-language artists whose names did not align exactly with the artist table. Because the missingness is explained by an observed column (`track_genre`), `followers` is classified as **MAR**.

## Hypothesis Testing

I tested whether tracks by artists in the highest follower quintile are more likely to be highly popular than tracks by artists in the lowest follower quintile.

- **Null hypothesis:** the high-follower and low-follower groups have the same probability of producing a highly popular track.
- **Alternative hypothesis:** the high-follower group has a higher probability of producing a highly popular track.
- **Test statistic:** difference in highly popular track rate, high-follower group minus low-follower group.
- **Significance level:** 0.05.

| metric | value |
| --- | --- |
| lowest_follower_popular_rate | 0.05 |
| highest_follower_popular_rate | 0.21 |
| observed_difference | 0.16 |
| p_value | 0.001 |

<iframe src="assets/hypothesis-null-distribution.html" width="100%" height="520" frameborder="0"></iframe>

The p-value is below 0.05, so I reject the null hypothesis. The data provide evidence that tracks by artists in the highest follower quintile are more likely to be highly popular than tracks by artists in the lowest follower quintile.

## Framing a Prediction Problem

I frame the prediction task as binary classification: predict whether `popular_70` is true. This is a classification problem because the response is a yes/no label. I evaluate models primarily with F1-score because the positive class is uncommon: only about 9% of the train and test rows are highly popular. Accuracy alone would overstate model quality.

The train/test split uses 3,750 training rows and 1,250 test rows. Both splits have a positive rate of about 0.09.

## Baseline Model

The baseline model is a logistic regression classifier using two original features: 1 quantitative and 1 nominal (0 ordinal).

- `followers` — **quantitative**: artist follower count, median-imputed and standardized before fitting
- `track_genre` — **nominal**: genre label, one-hot encoded with unknown handling

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

| metric | baseline_logistic_regression | final_random_forest |
| --- | --- | --- |
| accuracy | 0.63 | 0.79 |
| balanced_accuracy | 0.66 | 0.65 |
| f1 | 0.25 | 0.29 |
| precision | 0.15 | 0.2 |
| recall | 0.71 | 0.49 |

<iframe src="assets/model-comparison.html" width="100%" height="480" frameborder="0"></iframe>

The final random forest improves F1-score from 0.25 to 0.29 and improves precision from 0.15 to 0.20. It gives up some recall, but its positive predictions are more reliable than the baseline's.

## Fairness Analysis

I evaluated whether the final model performs worse for older tracks than for newer tracks. Group X is tracks released before the median release year in the test set, and Group Y is tracks released in or after the median year. I use recall parity because false negatives are costly in this framing: a model that misses popular tracks for one release era is less useful for that group.

| group | n_tracks | positive_rate | recall |
| --- | --- | --- | --- |
| older_than_1995 | 620 | 0.04 | 0.18 |
| newer_or_1995_and_after | 630 | 0.14 | 0.56 |

<iframe src="assets/fairness-recall.html" width="100%" height="480" frameborder="0"></iframe>

The observed recall gap is 0.381 in favor of newer tracks, with a permutation-test p-value of 0.001. I reject the null hypothesis of equal recall. The model appears to have lower recall for older tracks in this test set. This does not prove intentional bias, but it suggests that release-era effects should be monitored if the model is used for decision-making.

## Conclusion

Artist reach is informative for Spotify track popularity, but it is not sufficient by itself. Genre and audio features add useful context, and a random forest with engineered features performs better than a simple logistic-regression baseline. The strongest limitation is the high number of zero-popularity tracks, which may reflect data collection or Spotify availability effects rather than true listener demand.
