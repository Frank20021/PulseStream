import { useEffect, useState } from "react";
import {
  fetchCatalogUsers,
  fetchEventsPerMinute,
  fetchRecommendations,
  fetchSummary,
  type CatalogUser,
  type Recommendations,
  type Summary,
} from "./api";

const EMPTY: Summary = {
  total_events: 0,
  events_last_minute: 0,
  events_per_second: 0,
  active_users_last_window: 0,
  window_minutes: 5,
  rolling_five_minute_engagement: 0,
  job_click_through_rate: 0,
  connection_requests_this_hour: 0,
  trending_posts: [],
  trending_jobs: [],
  events_by_device: {},
  events_by_source: {},
  duplicate_events: 0,
  dead_letters: 0,
  retries: 0,
  consumer_lag: 0,
  failed_events: 0,
};

function formatNumber(value: number): string {
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function App() {
  const [summary, setSummary] = useState<Summary>(EMPTY);
  const [perMinute, setPerMinute] = useState<{ minute: string; count: number }[]>([]);
  const [users, setUsers] = useState<CatalogUser[]>([]);
  const [userId, setUserId] = useState("user_001");
  const [recs, setRecs] = useState<Recommendations | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");

  useEffect(() => {
    fetchCatalogUsers()
      .then(setUsers)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [nextSummary, nextMinutes, nextRecs] = await Promise.all([
          fetchSummary(),
          fetchEventsPerMinute(),
          fetchRecommendations(userId),
        ]);
        if (cancelled) {
          return;
        }
        setSummary(nextSummary);
        setPerMinute(nextMinutes.minutes);
        setRecs(nextRecs);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Load failed");
        }
      }
    }

    load();
    const timer = window.setInterval(load, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [userId]);

  const maxMinute = Math.max(1, ...perMinute.map((row) => row.count));

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Professional activity analytics</p>
          <h1>PulseStream</h1>
          <p className="lede">
            Live counters from Kafka consumers, Redis rolling windows, and PostgreSQL.
          </p>
        </div>
        <div className="status">
          <span className={error ? "dot down" : "dot up"} />
          {error ? error : `Live · ${updatedAt || "connecting"}`}
        </div>
      </header>

      <section className="kpis">
        <Kpi label="Events processed" value={formatNumber(summary.total_events)} />
        <Kpi label="Events / sec" value={formatNumber(summary.events_per_second)} />
        <Kpi label="Active users (5m)" value={formatNumber(summary.active_users_last_window)} />
        <Kpi label="Job CTR" value={percent(summary.job_click_through_rate)} />
        <Kpi label="Consumer lag" value={formatNumber(summary.consumer_lag)} />
        <Kpi label="Failed events" value={formatNumber(summary.failed_events)} />
        <Kpi label="Duplicates" value={formatNumber(summary.duplicate_events)} />
        <Kpi label="Retries" value={formatNumber(summary.retries)} />
      </section>

      <section className="grid">
        <article className="card wide">
          <h2>Events per minute</h2>
          <div className="bars">
            {perMinute.map((row) => (
              <div className="bar-col" key={row.minute}>
                <div
                  className="bar"
                  style={{ height: `${Math.max(4, (row.count / maxMinute) * 100)}%` }}
                  title={`${row.minute}: ${row.count}`}
                />
                <span>{row.minute.slice(-5)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card wide recs">
          <div className="recs-head">
            <div>
              <h2>Job recommendations</h2>
              <p className="empty">
                {recs?.formula ?? "0.50 * skill + 0.30 * interaction + 0.20 * popularity"}
              </p>
            </div>
            <label>
              User
              <select value={userId} onChange={(event) => setUserId(event.target.value)}>
                {(users.length ? users : [{ user_id: userId, skills: [] }]).map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.user_id}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {recs ? <RecommendationList recs={recs} /> : <p className="empty">Loading recommendations.</p>}
        </article>

        <article className="card">
          <h2>Trending posts</h2>
          <Ranked items={summary.trending_posts} idKey="post_id" />
        </article>

        <article className="card">
          <h2>Trending jobs</h2>
          <Ranked items={summary.trending_jobs} idKey="job_id" />
        </article>

        <article className="card">
          <h2>By device</h2>
          <Pairs data={summary.events_by_device} />
        </article>

        <article className="card">
          <h2>By source</h2>
          <Pairs data={summary.events_by_source} />
        </article>

        <article className="card">
          <h2>Operations</h2>
          <ul className="ops">
            <li>
              <span>Dead letters</span>
              <strong>{formatNumber(summary.dead_letters)}</strong>
            </li>
            <li>
              <span>5m engagement</span>
              <strong>{formatNumber(summary.rolling_five_minute_engagement)}</strong>
            </li>
            <li>
              <span>Connection requests (hour)</span>
              <strong>{formatNumber(summary.connection_requests_this_hour)}</strong>
            </li>
            <li>
              <span>Events last minute</span>
              <strong>{formatNumber(summary.events_last_minute)}</strong>
            </li>
          </ul>
        </article>
      </section>
    </div>
  );
}

function RecommendationList({ recs }: { recs: Recommendations }) {
  return (
    <div>
      <p className="rec-meta">
        Skills: {recs.skills.join(", ") || "none"}
        {recs.clicked_jobs.length ? ` · clicked ${recs.clicked_jobs.join(", ")}` : ""}
        {recs.saved_jobs.length ? ` · saved ${recs.saved_jobs.join(", ")}` : ""}
        {recs.similar_users.length ? ` · similar ${recs.similar_users.slice(0, 3).join(", ")}` : ""}
      </p>
      {recs.jobs.length === 0 ? (
        <p className="empty">No remaining jobs to recommend for this user.</p>
      ) : (
        <ol className="rec-list">
          {recs.jobs.map((job) => (
            <li key={job.job_id}>
              <div>
                <strong>
                  {job.title} · {job.company}
                </strong>
                <span className="rec-id">{job.job_id}</span>
                <span className="tags">
                  {job.skills.map((skill) => (
                    <em key={skill}>{skill}</em>
                  ))}
                </span>
                <span className="reasons">{job.reasons.join(" · ") || "Ranked by popularity"}</span>
              </div>
              <div className="rec-score">
                <strong>{job.score.toFixed(2)}</strong>
                <span>
                  s {job.skill_similarity.toFixed(2)} · i {job.interaction_similarity.toFixed(2)} · p{" "}
                  {job.popularity_score.toFixed(2)}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Ranked({
  items,
  idKey,
}: {
  items: { post_id?: string; job_id?: string; score: number }[];
  idKey: "post_id" | "job_id";
}) {
  if (items.length === 0) {
    return <p className="empty">No activity in this window yet.</p>;
  }
  return (
    <ol>
      {items.map((item) => (
        <li key={String(item[idKey])}>
          <span>{item[idKey]}</span>
          <strong>{item.score}</strong>
        </li>
      ))}
    </ol>
  );
}

function Pairs({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <p className="empty">No breakdown yet.</p>;
  }
  return (
    <ol>
      {entries.map(([label, value]) => (
        <li key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </li>
      ))}
    </ol>
  );
}
