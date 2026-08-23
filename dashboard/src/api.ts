export type TrendingItem = {
  post_id?: string;
  job_id?: string;
  score: number;
};

export type Summary = {
  total_events: number;
  events_last_minute: number;
  events_per_second: number;
  active_users_last_window: number;
  window_minutes: number;
  rolling_five_minute_engagement: number;
  job_click_through_rate: number;
  connection_requests_this_hour: number;
  trending_posts: TrendingItem[];
  trending_jobs: TrendingItem[];
  events_by_device: Record<string, number>;
  events_by_source: Record<string, number>;
  duplicate_events: number;
  dead_letters: number;
  retries: number;
  consumer_lag: number;
  failed_events: number;
};

export type EventsPerMinute = {
  minutes: { minute: string; count: number }[];
};

export type CatalogUser = {
  user_id: string;
  skills: string[];
};

export type RecommendedJob = {
  job_id: string;
  title: string;
  company: string;
  skills: string[];
  score: number;
  skill_similarity: number;
  interaction_similarity: number;
  popularity_score: number;
  reasons: string[];
};

export type Recommendations = {
  user_id: string;
  skills: string[];
  clicked_jobs: string[];
  saved_jobs: string[];
  similar_users: string[];
  formula: string;
  jobs: RecommendedJob[];
};

export async function fetchSummary(): Promise<Summary> {
  const response = await fetch("/api/v1/analytics/summary");
  if (!response.ok) {
    throw new Error("Could not load analytics summary");
  }
  return response.json();
}

export async function fetchEventsPerMinute(): Promise<EventsPerMinute> {
  const response = await fetch("/api/v1/analytics/events-per-minute?minutes=15");
  if (!response.ok) {
    throw new Error("Could not load events per minute");
  }
  return response.json();
}

export async function fetchCatalogUsers(): Promise<CatalogUser[]> {
  const response = await fetch("/api/v1/recommendations/users");
  if (!response.ok) {
    throw new Error("Could not load users");
  }
  const data = (await response.json()) as { users: CatalogUser[] };
  return data.users;
}

export async function fetchRecommendations(userId: string): Promise<Recommendations> {
  const response = await fetch(
    `/api/v1/recommendations/jobs?user_id=${encodeURIComponent(userId)}&limit=5`,
  );
  if (!response.ok) {
    throw new Error("Could not load recommendations");
  }
  return response.json();
}
