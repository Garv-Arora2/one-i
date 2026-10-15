/**
 * Split wording by the *language* used, not by a verdict on the outlet.
 *
 * Critical / favourable lists are auditable word lists. They describe the
 * verb or phrase on the page (attacked vs retaliated, pushed vs approved).
 * They are not a sentiment score of the publisher.
 */

const CRITICAL = new Set(
  `
mishandled botched failed failure inadequate insufficient chaotic slow sluggish
criticised criticized condemned troubling alarming catastrophic devastating
deadly fatal severe serious critical major massive widespread
attacked attacks attack struck strike strikes pushed pushes push protested
protests protest blamed blames denied denies rejected rejects reject blocked
blocks block killed shut
invaded invades invade bombed bombs bomb raided raids raid seized seizes seize
arrested arrests arrest detained detains detain expelled ousted toppled
destroyed destroys destroy wounded
  `.split(/\s+/).filter(Boolean),
);

const FAVOURABLE = new Set(
  `
praised swift prompt effective successful decisive commended reassuring
moderate limited minor small slight contained isolated
approved approves approve retaliated retaliates retaliate responded responds
respond agreed agrees agree restored restores restore reopened reopens reopen
rescued rescues rescue freed frees free released releases release
eased eases ease lifted lifts lift welcomed welcomes welcome
pledged pledges pledge vowed vows vow promised promises promise
defended defends defend backed backs back supported supports support
endorsed endorses endorse hailed hails hail
  `.split(/\s+/).filter(Boolean),
);

export type Lean = "harsh" | "softer" | "neither";

export function wordValence(word: string): Lean {
  const w = word.toLowerCase();
  if (CRITICAL.has(w)) return "harsh";
  if (FAVOURABLE.has(w)) return "softer";
  return "neither";
}

export function passageLean(markers: Record<string, string[]>): Lean {
  const words = Object.values(markers).flat().map((w) => w.toLowerCase());
  let harsh = 0;
  let softer = 0;
  for (const word of words) {
    if (CRITICAL.has(word)) harsh += 1;
    if (FAVOURABLE.has(word)) softer += 1;
  }
  if (harsh > softer) return "harsh";
  if (softer > harsh) return "softer";
  return "neither";
}

export function groupValence(
  verb: string,
  passages: { markers: Record<string, string[]> }[],
): Lean {
  const fromVerb = wordValence(verb);
  if (fromVerb !== "neither") return fromVerb;
  let harsh = 0;
  let softer = 0;
  for (const passage of passages) {
    const lean = passageLean(passage.markers);
    if (lean === "harsh") harsh += 1;
    if (lean === "softer") softer += 1;
  }
  if (harsh > softer) return "harsh";
  if (softer > harsh) return "softer";
  return "neither";
}
