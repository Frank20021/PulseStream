from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shared.database.models import CatalogJob, CatalogUser, Event
from shared.database.session import init_db, open_session
from shared.recommendations.catalog import JOBS, USERS
from shared.recommendations.scoring import Interaction, Interactions, recommend


def ensure_catalog() -> None:
    init_db()
    session = open_session()
    try:
        for profile in USERS.values():
            stmt = insert(CatalogUser).values(
                user_id=profile.user_id,
                skills=sorted(profile.skills),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id"],
                set_={"skills": stmt.excluded.skills},
            )
            session.execute(stmt)
        for profile in JOBS.values():
            stmt = insert(CatalogJob).values(
                job_id=profile.job_id,
                title=profile.title,
                company=profile.company,
                skills=sorted(profile.skills),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["job_id"],
                set_={
                    "title": stmt.excluded.title,
                    "company": stmt.excluded.company,
                    "skills": stmt.excluded.skills,
                },
            )
            session.execute(stmt)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_interactions() -> Interactions:
    session = open_session()
    try:
        rows = session.execute(
            select(Event.user_id, Event.event_type, Event.target_id).where(
                Event.event_type.in_(("job_view", "job_click", "job_save"))
            )
        ).all()
    finally:
        session.close()

    interactions: Interactions = {}
    for user_id, event_type, job_id in rows:
        user_jobs = interactions.setdefault(user_id, {})
        item = user_jobs.setdefault(job_id, Interaction())
        if event_type == "job_view":
            item.views += 1
        elif event_type == "job_click":
            item.clicks += 1
        else:
            item.saves += 1
    return interactions


def recommend_jobs(user_id: str, limit: int = 5) -> dict:
    return recommend(
        user_id,
        users=USERS,
        jobs=JOBS,
        interactions=load_interactions(),
        limit=limit,
    )
