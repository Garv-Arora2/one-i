/**
 * Split a crux part into readable bullets.
 * Key developments and reported numbers are stored as one packed string.
 */
export function cruxBulletItems(label: string, text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  if (label === "Key developments") {
    const parts = trimmed.split(/\s*\d+\.\s+/).map((s) => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts : [trimmed];
  }

  if (label === "Reported numbers") {
    const parts = trimmed.split(/;\s*/).map((s) => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts : [trimmed];
  }

  if (label === "Who is involved") {
    const parts = trimmed.split(/,\s*/).map((s) => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts : [trimmed];
  }

  const sentences = trimmed.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
  return sentences.length > 1 ? sentences : [trimmed];
}
