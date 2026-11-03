import { productName } from "../i18n/strings";

type Shape = "round" | "leaf" | "long" | "bulb";
const looks: Record<string, { shape: Shape; color: string }> = {
  TOMATO: { shape: "round", color: "#d84315" },
  SPINACH: { shape: "leaf", color: "#2e7d32" },
  BANANA: { shape: "long", color: "#f9a825" },
  ONION: { shape: "bulb", color: "#8e4585" },
  MANGO: { shape: "round", color: "#fb8c00" },
};
const fallback = { shape: "round" as Shape, color: "#6d7f5c" };

/** A drawn picture of the product. Name is read by screen readers; the picture carries meaning. */
export function ProductIcon({ skuId, size = 96 }: { skuId: string; size?: number }) {
  const { shape, color } = looks[skuId] ?? fallback;
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
      {shape === "bulb" && (
        <>
          <path d="M32 18c-14 6-18 18-12 28 4 6 20 6 24 0 6-10 2-22-12-28z" fill={color} />
          <path d="M32 18c-2-4-2-8 0-10M32 18c4-2 6-6 6-9" stroke="#a1887f" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}
