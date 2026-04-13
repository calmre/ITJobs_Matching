import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    df["salary_from"] = df["salary_from"].clip(upper=500_000)
    df["salary_to"] = df["salary_to"].clip(upper=500_000)
    df["salary_mid"] = (df["salary_from"] + df["salary_to"]) / 2

    df["tech_specialisation"] = df["tech_specialisation"].fillna("")
    df["level"] = df["level"].fillna("Unspecified")
    df["mode"] = df["mode"].fillna("Unspecified")
    df["type"] = df["type"].fillna("Unspecified")
    df["education_level"] = df["education_level"].fillna("Unspecified")
    df["type"] = df["type"].str.strip().str.title()

    return df


def match_jobs(
    df: pd.DataFrame,
    skill_query: str,
    level: list,
    mode: list,
    job_type: list,
    exp_years: float,
    salary_min: float,
    salary_max: float,
    top_n: int = 10,
) -> pd.DataFrame:
    candidates = df.copy()

    if level:
        candidates = candidates[candidates["level"].isin(level)]
    if mode:
        candidates = candidates[candidates["mode"].isin(mode)]
    if job_type:
        candidates = candidates[candidates["type"].isin(job_type)]

    candidates = candidates[
        (candidates["salary_mid"] >= salary_min) &
        (candidates["salary_mid"] <= salary_max)
    ]

    if candidates.empty:
        return pd.DataFrame()

    if skill_query.strip():
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        job_vectors = vectorizer.fit_transform(candidates["tech_specialisation"])
        query_vector = vectorizer.transform([skill_query])
        similarity_scores = cosine_similarity(query_vector, job_vectors).flatten()
        candidates = candidates.copy()
        candidates["skill_score"] = similarity_scores * 60
    else:
        candidates = candidates.copy()
        candidates["skill_score"] = 30.0

    def salary_score(mid):
        if salary_min <= mid <= salary_max:
            return 25.0
        if mid < salary_min:
            gap = salary_min - mid
            return max(0, 25 - (gap / salary_min) * 25) if salary_min > 0 else 0
        gap = mid - salary_max
        return max(0, 25 - (gap / salary_max) * 25) if salary_max > 0 else 0

    candidates["salary_score"] = candidates["salary_mid"].apply(salary_score)

    def exp_score(req_exp):
        if pd.isna(req_exp):
            return 7.5
        diff = abs(req_exp - exp_years)
        return max(0.0, 15.0 - diff * 3.0)

    candidates["exp_score"] = candidates["work_experience_years"].apply(exp_score)

    candidates["match_score"] = (
        candidates["skill_score"] +
        candidates["salary_score"] +
        candidates["exp_score"]
    ).round(1)
    candidates["match_pct"] = candidates["match_score"].clip(upper=100).astype(int)

    result = candidates.sort_values("match_pct", ascending=False).head(top_n)

    return result[[
        "jobid", "tech_specialisation", "level", "mode", "type",
        "salary_from", "salary_to", "salary_mid",
        "work_experience_years", "education_level",
        "match_pct", "skill_score", "salary_score", "exp_score",
    ]].reset_index(drop=True)
