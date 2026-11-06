// Icons drawn for this project (simple shapes, no third-party artwork).
import type { ReactNode } from "react";

export type IconName =
  | "tick" | "cross" | "plus" | "minus" | "cloud-rain" | "sun" | "lamp" | "clock" | "calendar"
  | "alert" | "triangle" | "tag" | "van" | "bag" | "crate" | "chat" | "mic-off" | "stop"
  | "home" | "moon" | "box" | "tractor" | "store" | "chart" | "coin" | "back" | "send" | "hourglass" | "rule" | "lock" | "logout" | "phone";

const paths: Record<IconName, ReactNode> = {
  tick: <path d="M4 13l5 5L20 6" />,
  cross: <path d="M5 5l14 14M19 5L5 19" />,
  plus: <path d="M12 4v16M4 12h16" />,
  minus: <path d="M4 12h16" />,
  "cloud-rain": (
    <>
      <path d="M7 14a4 4 0 010-8 5 5 0 019.6 1.2A3.4 3.4 0 0117 14z" />
      <path d="M8 17l-1 3M12 17l-1 3M16 17l-1 3" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
    </>
  ),
  lamp: (
    <>
      <path d="M12 2v3" />
      <path d="M8 5h8l2 6a6 6 0 01-12 0z" />
      <path d="M10 17l-1 4h6l-1-4" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  calendar: (
    <>
      <rect x="4" y="5" width="16" height="15" rx="2" />
      <path d="M4 10h16M8 3v4M16 3v4" />
    </>
  ),
  alert: (
    <>
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v5M12 18v.5" />
    </>
  ),
  triangle: <path d="M12 4l9 16H3z" />,
  tag: (
    <>
      <path d="M3 12V4h8l10 10-8 8z" />
      <circle cx="7.5" cy="8.5" r="1.3" />
    </>
  ),
  van: (
    <>
      <path d="M2 6h12v10H2zM14 9h5l3 4v3h-8z" />
      <circle cx="7" cy="18" r="2" />
      <circle cx="18" cy="18" r="2" />
    </>
  ),
  bag: (
    <>
      <path d="M5 8h14l-1 13H6z" />
      <path d="M9 8V6a3 3 0 016 0v2" />
    </>
  ),
  crate: (
    <>
      <path d="M3 8h18v11H3z" />
      <path d="M3 12h18M3 16h18M8 8v11M16 8v11" />
    </>
  ),
  chat: <path d="M4 5h16v11H10l-5 4v-4H4z" />,
  "mic-off": (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0014 0M12 18v3M4 4l16 16" />
    </>
  ),
  stop: <path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z" />,
  home: <path d="M3 11l9-8 9 8M6 10v10h12V10" />,
  moon: <path d="M20 14A8 8 0 0110 4a8 8 0 1010 10z" />,
  box: (
    <>
      <path d="M3 7l9-4 9 4v10l-9 4-9-4z" />
      <path d="M3 7l9 4 9-4M12 11v10" />
    </>
  ),
  tractor: (
    <>
      <path d="M3 17V9h9l2 4h6v4" />
      <circle cx="7" cy="17" r="3" />
      <circle cx="18" cy="17" r="2" />
    </>
  ),
  store: (
    <>
      <path d="M3 9l2-5h14l2 5zM4 9v11h16V9" />
      <path d="M10 20v-6h4v6" />
    </>
  ),
  chart: <path d="M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6" />,
  coin: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10M9 10c0-2 6-2 6 0s-6 2-6 4 6 2 6 0" />
    </>
  ),
  back: <path d="M15 5l-7 7 7 7" />,
  send: <path d="M3 12l18-8-6 16-3-7z" />,
  hourglass: <path d="M6 3h12M6 21h12M7 3c0 6 10 6 10 18M17 3c0 6-10 6-10 18" />,
  lock: (
    <>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 018 0v3" />
    </>
  ),
  logout: <path d="M9 4H4v16h5M14 8l4 4-4 4M18 12H8" />,
  phone: <path d="M6 3h4l2 5-3 2a12 12 0 005 5l2-3 5 2v4a2 2 0 01-2 2A17 17 0 013 5a2 2 0 013-2z" />,
  rule: (
    <>
      <path d="M5 3h14v18H5z" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
};

export function Icon({ name, size = 28, filled = false }: { name: IconName; size?: number; filled?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}
