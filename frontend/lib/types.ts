/** Types mirroring the ONE I API responses. */

export type CoverageStatus =
  | "covered"
  | "unclear"
  | "not_covered"
  | "not_applicable";

export interface SourceRef {
  id: number;
  name: string;
  domain: string;
  source_type: string;
}

export interface ArticleRef {
  id: number;
  title: string;
  url: string;
  published_at: string | null;
  source: SourceRef;
  /** Title is Wikipedia's summary of the report, not the outlet's headline. */
  title_is_summary: boolean;
}

export interface CruxPart {
  label: string;
  text: string;
  article_ids: number[];
}

export interface EventSummary {
  id: number;
  slug: string;
  title: string;
  crux: string | null;
  event_time: string | null;
  location: string | null;
  is_demo: boolean;
  article_count: number;
  source_count: number;
  development_count: number;
  has_reactions: boolean;
  image_url?: string | null;
}

export interface EventDetail extends EventSummary {
  context: string | null;
  crux_parts: CruxPart[];
  context_parts: CruxPart[];
  last_analyzed_at: string | null;
  articles: ArticleRef[];
}

export interface EventListResponse {
  events: EventSummary[];
  total: number;
}

export interface Development {
  id: number;
  title: string;
  short_title: string;
  description: string | null;
  occurred_at: string | null;
  importance: number;
  supporting_article_count: number;
  supporting_source_count: number;
  covered_by_source_count: number;
}

export interface TimelineResponse {
  event_id: number;
  developments: Development[];
  note: string | null;
}

export interface CoverageCell {
  development_id: number;
  source_id: number;
  status: CoverageStatus;
  similarity: number;
  matched_terms: string[];
  article_id: number | null;
  article_url: string | null;
}

export interface SourceCoverage {
  source: SourceRef;
  coverage_rate: number | null;
  covered: number;
  unclear: number;
  not_covered: number;
  not_applicable: number;
}

export interface CoverageResponse {
  event_id: number;
  developments: Development[];
  sources: SourceCoverage[];
  cells: CoverageCell[];
  overall_coverage_rate: number | null;
  note: string | null;
}

export interface NumberObservation {
  article_id: number;
  source: SourceRef;
  value: number;
  formatted_value: string;
  context: string;
  article_url: string;
}

export interface NumberComparison {
  subject: string;
  unit: string | null;
  value_kind: string;
  time_period: string | null;
  sources_agree: boolean;
  lowest: number;
  highest: number;
  difference: number;
  difference_unit: string;
  relative_difference_percent: number | null;
  observations: NumberObservation[];
}

export interface WordingPassage {
  article_id: number;
  source: SourceRef;
  article_url: string;
  quoted_text: string;
  surrounding_text: string | null;
  aspects: string[];
  markers: Record<string, string[]>;
}

export interface WordingComparison {
  topic: string;
  development_id: number | null;
  differing_aspects: string[];
  passages: WordingPassage[];
}

export interface ComparisonsResponse {
  event_id: number;
  numbers: NumberComparison[];
  wording: WordingComparison[];
  note: string | null;
}

export interface ReactionItem {
  platform: string;
  content: string;
  published_at: string | null;
  engagement: number;
  url: string | null;
  community: string | null;
}

export interface ReactionsResponse {
  event_id: number;
  available: boolean;
  unavailable_reason: string | null;
  total: number;
  by_platform: Record<string, { posts: number; engagement: number }>;
  timeline: { date: string; posts: number }[];
  highlights: ReactionItem[];
  disclaimer: string;
}

export interface SourceSummary {
  id: number;
  name: string;
  domain: string;
  source_type: string;
  is_demo: boolean;
  article_count: number;
  event_count: number;
}

export interface SourceEventCoverage {
  event_id: number;
  event_slug: string;
  event_title: string;
  event_time: string | null;
  article_count: number;
  coverage_rate: number | null;
  covered: number;
  unclear: number;
  not_covered: number;
  not_applicable: number;
}

export interface SourceDetail extends SourceSummary {
  events: SourceEventCoverage[];
}

export interface SourceListResponse {
  sources: SourceSummary[];
  total: number;
}

export interface AuthConfig {
  google_configured: boolean;
  captcha_provider: string;
  captcha_configured: boolean;
  dev_bypass_enabled: boolean;
  message: string;
}

export interface SessionResponse {
  authenticated: boolean;
  user: { id: number; email: string; name: string | null } | null;
}

export interface SystemStatus {
  environment: string;
  providers: {
    name: string;
    kind: string;
    configured: boolean;
    detail: string;
  }[];
  demo_events: number;
  live_events: number;
  note: string;
}
