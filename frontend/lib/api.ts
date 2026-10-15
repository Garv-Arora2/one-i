/**
 * Server-side API client.
 *
 * The browser never talks to the database and never runs analysis; every page
 * reads stored results through the FastAPI service.
 */

import type {
  AuthConfig,
  ComparisonsResponse,
  CoverageResponse,
  EventDetail,
  EventListResponse,
  ReactionsResponse,
  SourceDetail,
  SourceListResponse,
  SystemStatus,
  TimelineResponse,
} from "./types";

export const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

export class ApiUnavailableError extends Error {
  constructor(readonly path: string, readonly reason: string) {
    super(`ONE I API request to ${path} failed: ${reason}`);
    this.name = "ApiUnavailableError";
  }
}

export class NotFoundError extends Error {}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch (error) {
    throw new ApiUnavailableError(
      path,
      error instanceof Error ? error.message : "network error",
    );
  }

  if (response.status === 404) {
    throw new NotFoundError(path);
  }
  if (!response.ok) {
    throw new ApiUnavailableError(path, `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Returns null instead of throwing when the API is unreachable. */
export async function tryRequest<T>(path: string): Promise<T | null> {
  try {
    return await request<T>(path);
  } catch (error) {
    if (error instanceof NotFoundError) {
      return null;
    }
    console.error(error);
    return null;
  }
}

export const api = {
  events: (
    params: {
      limit?: number;
      offset?: number;
      dataset?: "all" | "demo" | "live";
      minSources?: number;
      sort?: "sources" | "recent" | "oldest";
    } = {},
  ) => {
    const query = new URLSearchParams();
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    if (params.dataset) {
      query.set("dataset", params.dataset);
    }
    if (params.minSources) {
      query.set("min_sources", String(params.minSources));
    }
    if (params.sort) {
      query.set("sort", params.sort);
    }
    return tryRequest<EventListResponse>(`/events?${query.toString()}`);
  },
  event: (reference: string) =>
    tryRequest<EventDetail>(`/events/${encodeURIComponent(reference)}`),
  timeline: (reference: string) =>
    tryRequest<TimelineResponse>(
      `/events/${encodeURIComponent(reference)}/timeline`,
    ),
  coverage: (reference: string) =>
    tryRequest<CoverageResponse>(
      `/events/${encodeURIComponent(reference)}/coverage`,
    ),
  comparisons: (reference: string) =>
    tryRequest<ComparisonsResponse>(
      `/events/${encodeURIComponent(reference)}/comparisons`,
    ),
  reactions: (reference: string) =>
    tryRequest<ReactionsResponse>(
      `/events/${encodeURIComponent(reference)}/reactions`,
    ),
  sources: () => tryRequest<SourceListResponse>("/sources"),
  source: (id: string) =>
    tryRequest<SourceDetail>(`/sources/${encodeURIComponent(id)}`),
  status: () => tryRequest<SystemStatus>("/status"),
  authConfig: () => tryRequest<AuthConfig>("/auth/config"),
};

/**
 * Base URL used by the browser: the same-origin proxy defined in
 * next.config.ts, so the session cookie belongs to this site.
 */
export const PUBLIC_API_BASE_URL = "/api";

export const SESSION_CHANGED_EVENT = "one-i:session-changed";
