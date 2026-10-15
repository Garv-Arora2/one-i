"use client";

import Image from "next/image";
import { useState } from "react";

import { FALLBACK_SRC, plateSrc, relatedImage, sizedSrc } from "@/lib/eventImage";
import type { EventSummary } from "@/lib/types";

import styles from "@/app/front.module.css";

const WIDTH: Record<"hero" | "medium" | "thumb", number> = {
  hero: 1400,
  medium: 800,
  thumb: 320,
};

export function StoryImage({
  event,
  size,
  variant = 0,
  caption = false,
}: {
  event: EventSummary;
  size: "hero" | "medium" | "thumb";
  variant?: number;
  caption?: boolean;
}) {
  const image = relatedImage(event, variant);
  // Broken photo -> spare photo -> local plate. The page never shows a
  // broken-image icon, even if the photo service throttles or blocks us.
  const [stage, setStage] = useState(0);
  const raw =
    stage === 0 ? image.src : stage === 1 ? FALLBACK_SRC : null;
  const src = raw === null ? plateSrc(event, variant) : sizedSrc(raw, WIDTH[size]);
  const showCaption = caption && image.related;
  return (
    <figure className={styles[`img_${size}`]}>
      <Image
        src={src}
        alt={stage < 2 ? image.alt : `Editorial plate for ${event.title}`}
        fill
        unoptimized
        sizes={
          size === "hero"
            ? "(max-width: 1000px) 100vw, 1100px"
            : size === "medium"
              ? "(max-width: 1000px) 100vw, 520px"
              : "120px"
        }
        priority={size === "hero"}
        onError={() => setStage((s) => (s < 2 ? s + 1 : s))}
      />
      {showCaption && (
        <figcaption className={styles.imgCaption}>
          Related image — not a photograph of this event
        </figcaption>
      )}
    </figure>
  );
}
