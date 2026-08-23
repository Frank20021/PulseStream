from dataclasses import dataclass

from shared.recommendations.catalog import JobProfile, UserProfile

SKILL_WEIGHT = 0.50
INTERACTION_WEIGHT = 0.30
POPULARITY_WEIGHT = 0.20
NEIGHBOR_LIMIT = 10

FORMULA = (
    f"{SKILL_WEIGHT:.2f} * skill_similarity"
    f" + {INTERACTION_WEIGHT:.2f} * interaction_similarity"
    f" + {POPULARITY_WEIGHT:.2f} * popularity_score"
)


@dataclass
class Interaction:
    views: int = 0
    clicks: int = 0
    saves: int = 0

    @property
    def clicked_or_saved(self) -> bool:
        return self.clicks > 0 or self.saves > 0

    def strength(self) -> float:
        if self.saves:
            return 1.0
        if self.clicks:
            return 0.7
        if self.views:
            return 0.3
        return 0.0


Interactions = dict[str, dict[str, Interaction]]


def jaccard(left: set[str] | frozenset[str], right: set[str] | frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def weighted_score(skill: float, interaction: float, popularity: float) -> float:
    return round(
        SKILL_WEIGHT * skill + INTERACTION_WEIGHT * interaction + POPULARITY_WEIGHT * popularity,
        4,
    )


def engaged_jobs(signals: dict[str, Interaction]) -> set[str]:
    engaged = {job_id for job_id, item in signals.items() if item.clicked_or_saved}
    if engaged:
        return engaged
    return {job_id for job_id, item in signals.items() if item.views}


def popularity_raw(job_id: str, interactions: Interactions) -> float:
    views = clicks = saves = 0
    for jobs in interactions.values():
        item = jobs.get(job_id)
        if item is None:
            continue
        views += item.views
        clicks += item.clicks
        saves += item.saves
    return float(views + 3 * clicks + 5 * saves)


def recommend(
    user_id: str,
    *,
    users: dict[str, UserProfile],
    jobs: dict[str, JobProfile],
    interactions: Interactions,
    limit: int = 5,
) -> dict:
    profile = users.get(user_id, UserProfile(user_id, frozenset()))
    own = interactions.get(user_id, {})
    clicked = sorted(job_id for job_id, item in own.items() if item.clicks)
    saved = sorted(job_id for job_id, item in own.items() if item.saves)
    excluded = set(clicked) | set(saved)
    own_engaged = engaged_jobs(own)
    own_skill_pool = _skill_pool(own_engaged, jobs)

    neighbor_ids, neighbor_sims = _neighbors(user_id, own_engaged, interactions)
    popularity_cap = max((popularity_raw(job_id, interactions) for job_id in jobs), default=0.0)

    ranked: list[dict] = []
    for job in jobs.values():
        if job.job_id in excluded:
            continue
        skill = jaccard(profile.skills, job.skills)
        content = jaccard(job.skills, own_skill_pool) if own_skill_pool else 0.0
        collaborative, neighbor_hits = _collaborative(
            job.job_id, neighbor_ids, neighbor_sims, interactions
        )
        if own_skill_pool and neighbor_ids:
            interaction = 0.5 * content + 0.5 * collaborative
        elif own_skill_pool:
            interaction = content
        else:
            interaction = collaborative
        popularity = 0.0 if popularity_cap <= 0 else popularity_raw(job.job_id, interactions) / popularity_cap
        ranked.append(
            {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "skills": sorted(job.skills),
                "score": weighted_score(skill, interaction, popularity),
                "skill_similarity": round(skill, 4),
                "interaction_similarity": round(interaction, 4),
                "popularity_score": round(popularity, 4),
                "reasons": _reasons(
                    job,
                    profile.skills,
                    own_engaged,
                    jobs,
                    neighbor_hits,
                    popularity,
                ),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {
        "user_id": user_id,
        "skills": sorted(profile.skills),
        "clicked_jobs": clicked,
        "saved_jobs": saved,
        "similar_users": neighbor_ids,
        "formula": FORMULA,
        "jobs": ranked[:limit],
    }


def _skill_pool(job_ids: set[str], jobs: dict[str, JobProfile]) -> set[str]:
    skills: set[str] = set()
    for job_id in job_ids:
        job = jobs.get(job_id)
        if job is not None:
            skills |= set(job.skills)
    return skills


def _neighbors(
    user_id: str,
    own_jobs: set[str],
    interactions: Interactions,
) -> tuple[list[str], dict[str, float]]:
    if not own_jobs:
        return [], {}
    scored: list[tuple[str, float]] = []
    for other_id, signals in interactions.items():
        if other_id == user_id:
            continue
        similarity = jaccard(own_jobs, engaged_jobs(signals))
        if similarity > 0:
            scored.append((other_id, similarity))
    scored.sort(key=lambda item: item[1], reverse=True)
    top = scored[:NEIGHBOR_LIMIT]
    return [user for user, _ in top], dict(top)


def _collaborative(
    job_id: str,
    neighbor_ids: list[str],
    neighbor_sims: dict[str, float],
    interactions: Interactions,
) -> tuple[float, int]:
    if not neighbor_ids:
        return 0.0, 0
    weighted = 0.0
    total = 0.0
    hits = 0
    for other_id in neighbor_ids:
        similarity = neighbor_sims[other_id]
        total += similarity
        item = interactions.get(other_id, {}).get(job_id)
        if item is None or item.strength() <= 0:
            continue
        weighted += similarity * item.strength()
        hits += 1
    if total <= 0:
        return 0.0, 0
    return weighted / total, hits


def _reasons(
    job: JobProfile,
    user_skills: frozenset[str],
    own_jobs: set[str],
    jobs: dict[str, JobProfile],
    neighbor_hits: int,
    popularity: float,
) -> list[str]:
    reasons: list[str] = []
    overlap = sorted(user_skills & job.skills)
    if overlap:
        reasons.append("Skills overlap: " + ", ".join(overlap))
    related = [
        job_id
        for job_id in sorted(own_jobs)
        if job_id in jobs and jobs[job_id].skills & job.skills
    ]
    if related:
        reasons.append("Similar to jobs you engaged: " + ", ".join(related[:3]))
    if neighbor_hits:
        noun = "user" if neighbor_hits == 1 else "users"
        reasons.append(f"{neighbor_hits} similar {noun} engaged with this job")
    if popularity >= 0.5:
        reasons.append("Popular across the network")
    return reasons
