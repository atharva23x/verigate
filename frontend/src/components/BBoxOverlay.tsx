/**
 * THE OVERLAY.
 *
 * Absolutely-positioned boxes drawn over a rendered document page. Every flag
 * produced by the pipeline carries a normalized [x, y, w, h] bounding box
 * (0..1, top-left origin) - we simply scale it to the container:
 *
 *   left: x * 100%   top: y * 100%   width: w * 100%   height: h * 100%
 *
 * Red    = CRITICAL anomaly (tamper region, expired field, missing doc...)
 * Orange = WARN (low-confidence field, issuer unavailable, consistency...)
 * Blue   = neutral highlight (clicked extracted field)
 */

export type OverlayTone = "red" | "orange" | "blue";

export interface OverlayBox {
  id: string;
  bbox: [number, number, number, number]; // normalized x, y, w, h
  tone: OverlayTone;
  label?: string;
  active?: boolean;
}

const TONE_CLS: Record<OverlayTone, string> = {
  red: "border-rose-500 bg-rose-500/20",
  orange: "border-amber-400 bg-amber-400/20",
  blue: "border-sky-400 bg-sky-400/20",
};

// Label chips match the box tone so the legend stays honest:
// red chip = critical, orange chip = warning, blue chip = a read field.
const TONE_LABEL_CLS: Record<OverlayTone, string> = {
  red: "bg-rose-600 text-white",
  orange: "bg-amber-500 text-amber-950",
  blue: "bg-sky-600 text-white",
};

export default function BBoxOverlay({ boxes }: { boxes: OverlayBox[] }) {
  return (
    <div className="pointer-events-none absolute inset-0">
      {boxes.map((b) => {
        const [x, y, w, h] = b.bbox;
        return (
          <div
            key={b.id}
            className={`absolute rounded-sm border-2 ${TONE_CLS[b.tone]} ${
              b.active ? "animate-pulsebox" : ""
            }`}
            style={{
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
            }}
            title={b.label}
          >
            {b.label && (
              <span
                className={`absolute -top-5 left-0 whitespace-nowrap rounded px-1 text-[9px] font-bold uppercase ${TONE_LABEL_CLS[b.tone]}`}
              >
                {b.label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
