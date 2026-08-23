from shared.recommendations.catalog import JOBS, USERS
from shared.recommendations.scoring import Interaction, jaccard, recommend, weighted_score


def test_jaccard_is_intersection_over_union() -> None:
    assert jaccard({"python", "kafka"}, {"kafka", "sql"}) == 1 / 3
    assert jaccard(set(), {"python"}) == 0.0
    assert jaccard({"python"}, set()) == 0.0


def test_weighted_score_uses_published_formula() -> None:
    assert weighted_score(1.0, 0.0, 0.0) == 0.5
    assert weighted_score(0.0, 1.0, 0.0) == 0.3
    assert weighted_score(0.0, 0.0, 1.0) == 0.2
    assert weighted_score(1.0, 1.0, 1.0) == 1.0


def test_saved_and_clicked_jobs_are_excluded() -> None:
    result = recommend(
        "user_001",
        users=USERS,
        jobs=JOBS,
        interactions={
            "user_001": {
                "job_001": Interaction(clicks=1),
                "job_010": Interaction(saves=1),
            }
        },
        limit=20,
    )
    ids = {job["job_id"] for job in result["jobs"]}
    assert "job_001" not in ids
    assert "job_010" not in ids
    assert result["clicked_jobs"] == ["job_001"]
    assert result["saved_jobs"] == ["job_010"]


def test_skill_overlap_ranks_backend_jobs_for_python_user() -> None:
    result = recommend("user_001", users=USERS, jobs=JOBS, interactions={}, limit=3)
    assert result["jobs"][0]["job_id"] == "job_001"
    assert result["jobs"][0]["skill_similarity"] == 1.0
    assert "python" in result["jobs"][0]["reasons"][0]


def test_similar_users_boost_a_job() -> None:
    interactions = {
        "user_001": {"job_001": Interaction(clicks=1)},
        "user_002": {
            "job_001": Interaction(clicks=1),
            "job_002": Interaction(saves=1),
        },
    }
    result = recommend(
        "user_001",
        users=USERS,
        jobs=JOBS,
        interactions=interactions,
        limit=12,
    )
    by_id = {job["job_id"]: job for job in result["jobs"]}
    assert "user_002" in result["similar_users"]
    assert by_id["job_002"]["interaction_similarity"] > 0
    assert any("similar" in reason for reason in by_id["job_002"]["reasons"])


def test_popularity_lifts_an_otherwise_unknown_job() -> None:
    result = recommend(
        "nobody",
        users=USERS,
        jobs=JOBS,
        interactions={
            "user_008": {"job_004": Interaction(views=20, clicks=10, saves=5)},
        },
        limit=1,
    )
    assert result["jobs"][0]["job_id"] == "job_004"
    assert result["jobs"][0]["popularity_score"] == 1.0
