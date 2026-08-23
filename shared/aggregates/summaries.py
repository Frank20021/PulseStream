import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert

from shared.analytics.metrics import click_through_rate
from shared.database import DailyJobMetric, DailyMetric, Event, FailedEvent, HourlyMetric, ScheduledReport
from shared.database.session import open_session

logger = logging.getLogger(__name__)


def _event_time():
    return func.coalesce(Event.processed_at, Event.received_at)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def truncate_hour(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def truncate_day(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def generate_hourly_summaries(hour_iso: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    if hour_iso:
        hours = [truncate_hour(_parse_iso(hour_iso))]
    else:
        current = truncate_hour(now)
        hours = [current - timedelta(hours=1), current]

    written = []
    session = open_session()
    try:
        for hour_start in hours:
            hour_end = hour_start + timedelta(hours=1)
            rows = session.execute(
                select(
                    Event.event_type,
                    func.count().label("event_count"),
                    func.count(func.distinct(Event.user_id)).label("unique_users"),
                )
                .where(_event_time() >= hour_start, _event_time() < hour_end)
                .group_by(Event.event_type)
            ).all()
            for row in rows:
                stmt = insert(HourlyMetric).values(
                    metric_hour=hour_start,
                    event_type=row.event_type,
                    event_count=row.event_count,
                    unique_users=row.unique_users,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["metric_hour", "event_type"],
                    set_={
                        "event_count": stmt.excluded.event_count,
                        "unique_users": stmt.excluded.unique_users,
                    },
                )
                session.execute(stmt)
                written.append(
                    {
                        "metric_hour": hour_start.isoformat(),
                        "event_type": row.event_type,
                        "event_count": row.event_count,
                        "unique_users": row.unique_users,
                    }
                )
        if written:
            session.add(
                ScheduledReport(
                    report_type="hourly_summary",
                    period_start=min(hours),
                    period_end=max(hour + timedelta(hours=1) for hour in hours),
                    payload={"rows": written},
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("hourly_summaries_written", extra={"row_count": len(written)})
    return {"rows": written}


def generate_daily_summaries(day_iso: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    if day_iso:
        days = [truncate_day(_parse_iso(day_iso))]
    else:
        today = truncate_day(now)
        days = [today - timedelta(days=1), today]

    type_rows: list[dict] = []
    job_rows: list[dict] = []
    session = open_session()
    try:
        for day_start in days:
            day_end = day_start + timedelta(days=1)
            metrics = session.execute(
                select(
                    Event.event_type,
                    func.count().label("event_count"),
                    func.count(func.distinct(Event.user_id)).label("unique_users"),
                )
                .where(_event_time() >= day_start, _event_time() < day_end)
                .group_by(Event.event_type)
            ).all()
            for row in metrics:
                stmt = insert(DailyMetric).values(
                    metric_day=day_start,
                    event_type=row.event_type,
                    event_count=row.event_count,
                    unique_users=row.unique_users,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["metric_day", "event_type"],
                    set_={
                        "event_count": stmt.excluded.event_count,
                        "unique_users": stmt.excluded.unique_users,
                    },
                )
                session.execute(stmt)
                type_rows.append(
                    {
                        "metric_day": day_start.isoformat(),
                        "event_type": row.event_type,
                        "event_count": row.event_count,
                        "unique_users": row.unique_users,
                    }
                )

            jobs = session.execute(
                select(
                    Event.target_id,
                    func.sum(case((Event.event_type == "job_view", 1), else_=0)).label("views"),
                    func.sum(case((Event.event_type == "job_click", 1), else_=0)).label("clicks"),
                    func.sum(case((Event.event_type == "job_save", 1), else_=0)).label("saves"),
                )
                .where(
                    _event_time() >= day_start,
                    _event_time() < day_end,
                    Event.event_type.in_(("job_view", "job_click", "job_save")),
                )
                .group_by(Event.target_id)
            ).all()
            for row in jobs:
                views = int(row.views or 0)
                clicks = int(row.clicks or 0)
                saves = int(row.saves or 0)
                stmt = insert(DailyJobMetric).values(
                    metric_day=day_start,
                    job_id=row.target_id,
                    views=views,
                    clicks=clicks,
                    saves=saves,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["metric_day", "job_id"],
                    set_={"views": stmt.excluded.views, "clicks": stmt.excluded.clicks, "saves": stmt.excluded.saves},
                )
                session.execute(stmt)
                job_rows.append(
                    {
                        "metric_day": day_start.isoformat(),
                        "job_id": row.target_id,
                        "views": views,
                        "clicks": clicks,
                        "saves": saves,
                        "rate": click_through_rate(clicks, views),
                    }
                )

        session.add(
            ScheduledReport(
                report_type="daily_summary",
                period_start=min(days),
                period_end=max(day + timedelta(days=1) for day in days),
                payload={"event_types": type_rows, "jobs": job_rows},
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(
        "daily_summaries_written",
        extra={"event_type_rows": len(type_rows), "job_rows": len(job_rows)},
    )
    return {"event_types": type_rows, "jobs": job_rows}


def write_failure_report(hours: int = 24) -> dict:
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=hours)
    session = open_session()
    try:
        total = session.execute(select(func.count()).select_from(FailedEvent)).scalar_one()
        recent = session.execute(
            select(FailedEvent)
            .where(FailedEvent.failed_at >= period_start)
            .order_by(FailedEvent.failed_at.desc())
            .limit(20)
        ).scalars().all()
        payload = {
            "total_failed_events": total,
            "recent_count": len(recent),
            "window_hours": hours,
            "recent": [
                {
                    "event_id": row.event_id,
                    "retry_count": row.retry_count,
                    "error_message": row.error_message[:300],
                    "failed_at": row.failed_at.isoformat() if row.failed_at else None,
                }
                for row in recent
            ],
        }
        session.add(
            ScheduledReport(
                report_type="failure_report",
                period_start=period_start,
                period_end=now,
                payload=payload,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("failure_report_written", extra={"recent_count": payload["recent_count"]})
    return payload


def list_hourly_metrics(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    session = open_session()
    try:
        rows = session.execute(
            select(HourlyMetric)
            .where(HourlyMetric.metric_hour >= cutoff)
            .order_by(HourlyMetric.metric_hour.desc(), HourlyMetric.event_type)
        ).scalars().all()
        return [
            {
                "metric_hour": row.metric_hour.isoformat(),
                "event_type": row.event_type,
                "event_count": row.event_count,
                "unique_users": row.unique_users,
            }
            for row in rows
        ]
    finally:
        session.close()


def list_daily_metrics(days: int = 7) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    session = open_session()
    try:
        rows = session.execute(
            select(DailyMetric)
            .where(DailyMetric.metric_day >= cutoff)
            .order_by(DailyMetric.metric_day.desc(), DailyMetric.event_type)
        ).scalars().all()
        return [
            {
                "metric_day": row.metric_day.isoformat(),
                "event_type": row.event_type,
                "event_count": row.event_count,
                "unique_users": row.unique_users,
            }
            for row in rows
        ]
    finally:
        session.close()


def list_daily_job_metrics(days: int = 7) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    session = open_session()
    try:
        rows = session.execute(
            select(DailyJobMetric)
            .where(DailyJobMetric.metric_day >= cutoff)
            .order_by(DailyJobMetric.metric_day.desc(), DailyJobMetric.job_id)
        ).scalars().all()
        return [
            {
                "metric_day": row.metric_day.isoformat(),
                "job_id": row.job_id,
                "views": row.views,
                "clicks": row.clicks,
                "saves": row.saves,
                "rate": click_through_rate(row.clicks, row.views),
            }
            for row in rows
        ]
    finally:
        session.close()


def list_scheduled_reports(report_type: str | None = None, limit: int = 20) -> list[dict]:
    session = open_session()
    try:
        stmt = select(ScheduledReport).order_by(ScheduledReport.created_at.desc()).limit(limit)
        if report_type:
            stmt = stmt.where(ScheduledReport.report_type == report_type)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "report_type": row.report_type,
                "period_start": row.period_start.isoformat() if row.period_start else None,
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "payload": row.payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    finally:
        session.close()


def failed_event_count() -> int:
    session = open_session()
    try:
        return int(session.execute(select(func.count()).select_from(FailedEvent)).scalar_one())
    finally:
        session.close()
