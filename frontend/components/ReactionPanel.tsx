import { formatCount } from "@/lib/format";
import type { ReactionItem, ReactionsResponse } from "@/lib/types";

import styles from "./Panels.module.css";

function RedditLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="10" fill="#FF4500" />
      <circle cx="10" cy="11.2" r="6.2" fill="#fff" />
      <circle cx="7.4" cy="10.6" r="1.35" fill="#FF4500" />
      <circle cx="12.6" cy="10.6" r="1.35" fill="#FF4500" />
      <path d="M7.6 13.1c.7.7 1.6 1.05 2.4 1.05s1.7-.35 2.4-1.05" fill="none" stroke="#FF4500" strokeWidth="1.1" strokeLinecap="round" />
      <circle cx="14.6" cy="6.2" r="1.35" fill="#fff" />
      <path d="M12.2 8.1 L14.3 6.6" stroke="#fff" strokeWidth="1.2" />
    </svg>
  );
}

function YouTubeLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 28 20" aria-hidden="true">
      <rect width="28" height="20" rx="4.5" fill="#FF0000" />
      <path d="M11 5.5 L11 14.5 L19 10 Z" fill="#fff" />
    </svg>
  );
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const hours = Math.max(1, Math.round((Date.now() - then) / 36e5));
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function RedditPost({ h }: { h: ReactionItem }) {
  const sub = (h.community ?? "news").replace(/^r\//, "");
  return (
    <article className={styles.redditPost}>
      <div className={styles.redditVote} aria-hidden="true">
        <span className={styles.redditChevron}>▴</span>
        <span className={styles.redditScore}>{formatCount(h.engagement)}</span>
        <span className={styles.redditChevronDown}>▾</span>
      </div>
      <div className={styles.redditBody}>
        <p className={styles.redditMeta}>
          <RedditLogo className={styles.redditSnoo} />
          <span className={styles.redditSub}>r/{sub}</span>
          <span>· {timeAgo(h.published_at) || "posted"}</span>
        </p>
        <p className={styles.redditTitle}>
          {h.url ? (
            <a href={h.url} target="_blank" rel="noreferrer noopener">
              {h.content}
            </a>
          ) : (
            h.content
          )}
        </p>
        <p className={styles.redditActions}>Comment · Share · Save</p>
      </div>
    </article>
  );
}

function YouTubeComment({ h }: { h: ReactionItem }) {
  return (
    <article className={styles.ytComment}>
      <div className={styles.ytAvatar} aria-hidden="true">
        ?
      </div>
      <div>
        <p className={styles.ytMeta}>
          <span className={styles.ytAuthor}>Viewer</span>
          {h.community && <span>on a {h.community} video</span>}
          <span>{timeAgo(h.published_at)}</span>
        </p>
        <p className={styles.ytText}>
          {h.url ? (
            <a href={h.url} target="_blank" rel="noreferrer noopener">
              {h.content}
            </a>
          ) : (
            h.content
          )}
        </p>
        <p className={styles.ytActions}>
          <span>👍 {formatCount(h.engagement)}</span>
          <span>👎</span>
          <span>Reply</span>
        </p>
      </div>
    </article>
  );
}

export function ReactionPanel({ reactions }: { reactions: ReactionsResponse }) {
  const reddit = reactions.highlights.filter((h) => h.platform === "reddit");
  const youtube = reactions.highlights.filter((h) => h.platform === "youtube");

  const subredditCounts = new Map<string, number>();
  for (const h of reddit) {
    const name = (h.community ?? "reddit").replace(/^r\//, "");
    subredditCounts.set(name, (subredditCounts.get(name) ?? 0) + 1);
  }
  const topSubs = [...subredditCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div>
      <div className={`${styles.reactionGrid} ${reddit.length === 0 ? styles.reactionGridSingle : ""}`}>
        {reddit.length > 0 && (
        <section className={`${styles.platformCol} ${styles.redditCol}`}>
          <div className={styles.platformBrand}>
            <RedditLogo className={styles.brandLogo} />
            <div>
              <p className={styles.platformKicker}>Reddit</p>
              <h3 className={styles.platformTitle}>Top threads</h3>
            </div>
          </div>
          {topSubs.length > 0 && (
            <ul className={styles.subList}>
              {topSubs.map(([name, count]) => (
                <li key={name}>
                  <span className={styles.subName}>r/{name}</span>
                  <span className={styles.subCount}>{count}</span>
                </li>
              ))}
            </ul>
          )}
          {reddit.map((h, i) => (
            <RedditPost key={i} h={h} />
          ))}
        </section>
        )}

        <section className={`${styles.platformCol} ${styles.youtubeCol}`}>
          <div className={styles.platformBrand}>
            <YouTubeLogo className={styles.ytBrandLogo} />
            <div>
              <p className={styles.platformKicker}>YouTube</p>
              <h3 className={styles.platformTitle}>Most-liked comments</h3>
            </div>
          </div>
          {youtube.length > 0 ? (
            youtube.map((h, i) => <YouTubeComment key={i} h={h} />)
          ) : (
            <p className={styles.emptyPlat}>
              No YouTube comments about this event were found.
            </p>
          )}
        </section>
      </div>

      <p className={styles.disclaimer}>{reactions.disclaimer}</p>
    </div>
  );
}
