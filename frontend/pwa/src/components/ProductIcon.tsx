import { productName } from "../i18n/strings";

export type Shape = "round" | "leaf" | "long" | "bulb" | "oval" | "cone" | "cluster" | "half" | "pod" | "floret" | "coconut" | "pepper";
export const looks: Record<string, { shape: Shape; color: string }> = {
  // the five ids the demo and mock data use
  TOMATO: { shape: "round", color: "#d84315" },
  SPINACH: { shape: "leaf", color: "#2e7d32" },
  BANANA: { shape: "long", color: "#f9a825" },
  ONION: { shape: "bulb", color: "#8e4585" },
  MANGO: { shape: "oval", color: "#fb8c00" },
  // the 25 products of the product list
  P01: { shape: "round", color: "#d84315" },
  P02: { shape: "bulb", color: "#8e4585" },
  P03: { shape: "oval", color: "#a1887f" },
  P04: { shape: "long", color: "#f9a825" },
  P05: { shape: "long", color: "#fdd835" },
  P06: { shape: "round", color: "#c62828" },
  P07: { shape: "oval", color: "#fb8c00" },
  P08: { shape: "oval", color: "#ff8a50" },
  P09: { shape: "round", color: "#ad1457" },
  P10: { shape: "cluster", color: "#9ccc65" },
  P11: { shape: "half", color: "#2e7d32" },
  P12: { shape: "coconut", color: "#7cb342" },
  P13: { shape: "leaf", color: "#43a047" },
  P14: { shape: "leaf", color: "#2e7d32" },
  P15: { shape: "leaf", color: "#66bb6a" },
  P16: { shape: "leaf", color: "#1b5e20" },
  P17: { shape: "pod", color: "#2e7d32" },
  P18: { shape: "bulb", color: "#d7b98e" },
  P19: { shape: "cone", color: "#ef6c00" },
  P20: { shape: "pod", color: "#558b2f" },
  P21: { shape: "floret", color: "#f5f0e1" },
  P22: { shape: "floret", color: "#aed581" },
  P23: { shape: "pepper", color: "#43a047" },
  P24: { shape: "pod", color: "#689f38" },
  P25: { shape: "oval", color: "#fdd835" },
};
const fallback = { shape: "round" as Shape, color: "#6d7f5c" };

/** A drawn picture of the product. Name is read by screen readers; the picture carries meaning. */
export function ProductIcon({ skuId, size = 96 }: { skuId: string; size?: number }) {
  const { shape, color } = looks[skuId.toUpperCase()] ?? fallback;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={productName(skuId)}>
      <circle cx="32" cy="32" r="31" fill="#f1f8e9" />
      {shape === "round" && (
        <>
          <circle cx="32" cy="36" r="17" fill={color} />
          <path d="M32 19c-3-5-8-5-10-3 4 0 6 2 10 3zm0 0c3-5 8-5 10-3-4 0-6 2-10 3z" fill="#2e7d32" />
        </>
      )}
      {shape === "leaf" && (
        <>
          <path d="M14 44c0-18 14-28 36-28 0 20-12 32-26 32-6 0-10-2-10-4z" fill={color} />
          <path d="M16 46c8-8 18-16 30-26" stroke="#c8e6c9" strokeWidth="2.5" fill="none" />
        </>
      )}
      {shape === "long" && (
        <>
          <path d="M14 22c2 20 18 30 38 26-4-4-8-6-12-10-6-6-8-12-8-18z" fill={color} />
          <path d="M20 14l4 8" stroke="#6d4c41" strokeWidth="4" strokeLinecap="round" />
        </>
      )}
      {shape === "oval" && (
        <>
          <ellipse cx="32" cy="35" rx="21" ry="15" fill={color} transform="rotate(-18 32 35)" />
          <path d="M30 20c2-3 5-4 8-3-2 2-5 4-8 3z" fill="#2e7d32" />
        </>
      )}
      {shape === "cone" && (
        <>
          <path d="M16 24c4-6 12-6 16-2l16 22c2 4-2 8-6 6L18 34c-4-3-5-7-2-10z" fill={color} transform="rotate(-20 32 32) translate(2 4)" />
          <path d="M46 14c-2 4-4 6-8 8M50 20c-4 0-6 2-9 4M44 10c-1 4 0 6 2 9" stroke="#2e7d32" strokeWidth="3" fill="none" strokeLinecap="round" />
        </>
      )}
      {shape === "cluster" && (
        <>
          {[[22, 26], [32, 26], [42, 26], [27, 35], [37, 35], [32, 44], [27, 17]].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="6.5" fill={color} stroke="#7cb342" strokeWidth="1.5" />
          ))}
          <path d="M32 14c0-4 3-7 8-7" stroke="#6d4c41" strokeWidth="3" fill="none" strokeLinecap="round" />
        </>
      )}
      {shape === "half" && (
        <>
          <path d="M8 30h48a24 24 0 0 1-48 0z" fill={color} />
          <path d="M12 30h40a20 20 0 0 1-40 0z" fill="#e53935" />
          {[[24, 38], [32, 42], [40, 38], [32, 34]].map(([x, y]) => (
            <ellipse key={`${x}-${y}`} cx={x} cy={y} rx="1.8" ry="2.6" fill="#263238" />
          ))}
        </>
      )}
      {shape === "pod" && (
        <path d="M14 46C26 44 40 32 50 16" stroke={color} strokeWidth="9" strokeLinecap="round" fill="none" />
      )}
      {shape === "floret" && (
        <>
          {[[22, 34], [32, 28], [42, 34], [27, 42], [37, 42]].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="10" fill={color} stroke="#c5ca9c" strokeWidth="1.5" />
          ))}
          <path d="M14 38c4 12 32 12 36 0-6 4-30 4-36 0z" fill="#7cb342" />
        </>
      )}
      {shape === "coconut" && (
        <>
          <circle cx="32" cy="36" r="18" fill={color} />
          <path d="M32 18c-1-5-1-8 2-11" stroke="#6d4c41" strokeWidth="3" fill="none" strokeLinecap="round" />
          <ellipse cx="26" cy="30" rx="4" ry="6" fill="#ffffff" opacity="0.25" />
        </>
      )}
      {shape === "pepper" && (
        <>
          <path d="M16 28c0-8 8-10 16-6 8-4 16-2 16 6 0 12-6 22-16 22S16 40 16 28z" fill={color} />
          <path d="M32 22c0-4 1-7 4-9" stroke="#2e7d32" strokeWidth="3.5" fill="none" strokeLinecap="round" />
        </>
      )}
      {shape === "bulb" && (
        <>
          <path d="M32 18c-14 6-18 18-12 28 4 6 20 6 24 0 6-10 2-22-12-28z" fill={color} />
          <path d="M32 18c-2-4-2-8 0-10M32 18c4-2 6-6 6-9" stroke="#a1887f" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}
