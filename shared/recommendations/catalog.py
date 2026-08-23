from dataclasses import dataclass


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    skills: frozenset[str]


@dataclass(frozen=True)
class JobProfile:
    job_id: str
    title: str
    company: str
    skills: frozenset[str]


def _user(user_id: str, *skills: str) -> UserProfile:
    return UserProfile(user_id, frozenset(skills))


def _job(job_id: str, title: str, company: str, *skills: str) -> JobProfile:
    return JobProfile(job_id, title, company, frozenset(skills))


USERS: dict[str, UserProfile] = {
    profile.user_id: profile
    for profile in (
        _user("user_001", "python", "kafka", "postgresql", "redis"),
        _user("user_002", "python", "kafka", "sql"),
        _user("user_003", "python", "postgresql", "redis"),
        _user("user_004", "python", "kafka", "kubernetes"),
        _user("user_005", "python", "sql", "spark"),
        _user("user_006", "python", "sql", "dbt"),
        _user("user_007", "python", "pytorch", "ml"),
        _user("user_008", "typescript", "react", "css"),
        _user("user_009", "typescript", "react"),
        _user("user_010", "typescript", "css"),
        _user("user_011", "react", "typescript", "python"),
        _user("user_012", "typescript", "react", "postgresql"),
        _user("user_013", "swift", "ios"),
        _user("user_014", "swift", "ios"),
        _user("user_015", "kotlin", "android"),
        _user("user_016", "kotlin", "android"),
        _user("user_017", "python", "kubernetes", "kafka"),
        _user("user_018", "product", "sql"),
        _user("user_019", "python", "typescript", "react"),
        _user("user_020", "recruiting"),
    )
}

JOBS: dict[str, JobProfile] = {
    profile.job_id: profile
    for profile in (
        _job("job_001", "Backend Engineer", "Nimbus", "python", "kafka", "postgresql", "redis"),
        _job("job_002", "Data Engineer", "Northwind", "python", "sql", "spark"),
        _job("job_003", "ML Engineer", "Helios", "python", "pytorch", "ml"),
        _job("job_004", "Frontend Engineer", "Nimbus", "typescript", "react", "css"),
        _job("job_005", "iOS Engineer", "Helios", "swift", "ios"),
        _job("job_006", "SRE", "Northwind", "kubernetes", "linux", "kafka"),
        _job("job_007", "Product Manager", "Nimbus", "product", "sql"),
        _job("job_008", "Technical Recruiter", "Helios", "recruiting"),
        _job("job_009", "Full Stack Engineer", "Northwind", "python", "typescript", "react", "postgresql"),
        _job("job_010", "Platform Engineer", "Nimbus", "python", "kubernetes", "kafka"),
        _job("job_011", "Analytics Engineer", "Helios", "sql", "python", "dbt"),
        _job("job_012", "Android Engineer", "Northwind", "kotlin", "android"),
    )
}


def list_users() -> list[dict]:
    return [
        {"user_id": profile.user_id, "skills": sorted(profile.skills)}
        for profile in USERS.values()
    ]


def matching_jobs(user_id: str, job_ids: list[str]) -> list[str]:
    profile = USERS.get(user_id)
    if profile is None:
        return []
    matches = [
        job_id
        for job_id in job_ids
        if job_id in JOBS and JOBS[job_id].skills & profile.skills
    ]
    return matches
