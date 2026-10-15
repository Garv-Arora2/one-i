import type { EventSummary } from "./types";

export interface RelatedImage {
  src: string;
  alt: string;
  related: boolean;
}

/**
 * Public-domain / Unsplash scenes, matched by keywords in the title.
 *
 * Live RSS should set `image_url` on the event from the article enclosure or
 * Open Graph image. Until that field is present, ONE I uses a related scene
 * and says so in the caption. Images are not downloaded into the repo.
 */
const LIBRARY: { keys: string[]; src: string; alt: string }[] = [
  {
    keys: ["military", "army", "troops", "defence", "defense", "war", "missile", "airstrike", "drone", "shelling", "bombing", "ceasefire"],
    src: "https://images.unsplash.com/photo-1579912437766-7896df6d3cd3",
    alt: "Soldier in the field",
  },
  {
    keys: ["chemical", "leak", "plant", "factory", "industrial", "solvent", "evacuation", "vantor"],
    src: "https://images.unsplash.com/photo-1516937941344-00b4e0337589",
    alt: "Industrial plant",
  },
  {
    keys: ["housing", "homes", "home", "apartment", "residential", "harbourside", "rent"],
    src: "https://images.unsplash.com/photo-1560518883-ce09059eeffa",
    alt: "Housing",
  },
  {
    keys: ["harbour", "harbor", "port", "dock", "cargo", "ship"],
    src: "https://images.unsplash.com/photo-1578575437130-527eed3abbec",
    alt: "Container port",
  },
  {
    keys: ["president", "prime minister", "minister", "leader", "summit", "podium", "press conference"],
    src: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620",
    alt: "Public meeting",
  },
  {
    keys: ["council", "vote", "politics", "government", "parliament", "election"],
    src: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620",
    alt: "Public meeting",
  },
  {
    keys: ["market", "stock", "share", "trading", "price", "bank"],
    src: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3",
    alt: "Market screens",
  },
  {
    keys: ["court", "trial", "judge", "legal", "lawsuit"],
    src: "https://images.unsplash.com/photo-1589994965851-a8f479c573a9",
    alt: "Scales of justice",
  },
  {
    keys: ["hospital", "health", "patient", "doctor", "vaccine", "outbreak"],
    src: "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d",
    alt: "Hospital",
  },
  {
    keys: ["fire", "wildfire", "blaze"],
    src: "https://images.unsplash.com/photo-1615092296061-e2ccfeb2f3d6",
    alt: "Wildfire",
  },
  {
    keys: ["flood", "storm", "hurricane", "cyclone", "rain"],
    src: "https://images.unsplash.com/photo-1534088568595-a066f410bcda",
    alt: "Rain",
  },
  {
    keys: ["oil", "pipeline", "energy", "gas", "refinery", "diesel", "fuel"],
    src: "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e",
    alt: "Power lines",
  },
  {
    keys: ["school", "student", "education", "university", "campus"],
    src: "https://images.unsplash.com/photo-1580582932707-520aed937b7b",
    alt: "School",
  },
  {
    keys: ["airport", "flight", "airline", "aviation"],
    src: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05",
    alt: "Airport",
  },
  {
    keys: ["train", "rail", "railway", "metro", "truck", "highway", "freight", "supply chain", "logistics", "transport"],
    src: "https://images.unsplash.com/photo-1519003722824-194d4455a60c",
    alt: "Road freight",
  },
  {
    keys: ["police", "arrest", "crime", "investigation"],
    src: "https://images.unsplash.com/photo-1505664194779-8beaceb93744",
    alt: "Law",
  },
  {
    keys: ["climate", "emissions", "carbon", "warming"],
    src: "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05",
    alt: "Misty hills",
  },
  {
    keys: ["sport", "match", "stadium", "tournament", "olympic"],
    src: "https://images.unsplash.com/photo-1522778119026-d647f0596c20",
    alt: "Stadium",
  },
  {
    keys: ["tech", "software", "cyber", "computer", "ai"],
    src: "https://images.unsplash.com/photo-1518770660439-4636190af475",
    alt: "Circuit board",
  },
  {
    keys: ["office", "company", "ceo", "corporate", "business"],
    src: "https://images.unsplash.com/photo-1497366216548-37526070297c",
    alt: "Offices",
  },
  {
    keys: ["farm", "crop", "agriculture", "harvest"],
    src: "https://images.unsplash.com/photo-1500382017468-9049fed747ef",
    alt: "Farmland",
  },
  {
    keys: ["space", "rocket", "nasa", "satellite"],
    src: "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa",
    alt: "Earth from space",
  },
];

/** Spare photo when the matched scene fails to load. Verified alive. */
export const FALLBACK_SRC =
  "https://images.unsplash.com/photo-1504711434969-e33886168f5c";

const FALLBACKS: RelatedImage[] = [  {
    src: "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
    alt: "Newsroom",
    related: true,
  },
  {
    src: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab",
    alt: "City buildings",
    related: true,
  },
  {
    src: "https://images.unsplash.com/photo-1495020689067-958852a7765e",
    alt: "Newspapers",
    related: true,
  },
  {
    src: "https://images.unsplash.com/photo-1585829365295-ab7cd400c167",
    alt: "Broadcast studio",
    related: true,
  },
  {
    src: "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
    alt: "News desk",
    related: true,
  },
];

function haystack(event: EventSummary): string {
  return `${event.title} ${event.location ?? ""} ${event.slug}`.toLowerCase();
}

export function relatedImage(
  event: EventSummary,
  variant = 0,
): RelatedImage {
  if (event.image_url) {
    return { src: event.image_url, alt: event.title, related: false };
  }
  const text = haystack(event);
  // Whole words only: "airport" must not match "port", nor "ceasefire" "fire".
  const match = LIBRARY.find((entry) =>
    entry.keys.some((key) => new RegExp(`\\b${key}\\b`).test(text)),
  );
  if (match) {
    return { src: match.src, alt: match.alt, related: true };
  }
  return FALLBACKS[Math.abs(event.id + variant) % FALLBACKS.length];
}

export function sizedSrc(src: string, width: number): string {
  if (!src.includes("images.unsplash.com")) return src;
  const join = src.includes("?") ? "&" : "?";
  return `${src}${join}auto=format&fit=crop&w=${width}&q=75`;
}

/** A guaranteed-local editorial plate, used when every photo fails. */
export function plateSrc(event: EventSummary, variant = 0): string {
  const initial = (event.title.match(/[A-Za-z0-9]/)?.[0] || "O").toUpperCase();
  const tones = ["#a63a2b", "#1f5c4d", "#8a6d1d", "#26355c"];
  const tone = tones[Math.abs(event.id + variant) % tones.length];
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450">` +
    `<rect width="800" height="450" fill="#ece7db"/>` +
    `<rect x="14" y="14" width="772" height="422" fill="none" stroke="#221e19" stroke-width="3"/>` +
    `<circle cx="400" cy="195" r="105" fill="none" stroke="#221e19" stroke-width="10"/>` +
    `<line x1="478" y1="272" x2="560" y2="352" stroke="${tone}" stroke-width="22" stroke-linecap="round"/>` +
    `<text x="400" y="238" text-anchor="middle" font-family="Georgia, serif" font-size="120" font-weight="bold" fill="#221e19">${initial}</text>` +
    `<text x="400" y="392" text-anchor="middle" font-family="Georgia, serif" font-size="30" letter-spacing="6" fill="${tone}">ONE I &#183; RELATED IMAGE</text>` +
    `</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
