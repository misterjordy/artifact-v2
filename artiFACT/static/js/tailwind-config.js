"use strict";

tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: {
        sidebar: {
          DEFAULT: "#1e293b",
          hover: "rgba(255,255,255,0.08)",
          active: "rgba(255,255,255,0.12)",
        },
        accent: {
          DEFAULT: "#2563eb",
          hover: "#1d4ed8",
          light: "#dbeafe",
        },
      },
      fontSize: {
        /* Every text utility multiplied by --font-scale so the settings
           slider scales ALL text without touching layout (padding, gaps, widths). */
        "3xs": ["calc(9px * var(--font-scale, 1))",  { lineHeight: "1" }],
        "2xs": ["calc(10px * var(--font-scale, 1))", { lineHeight: "1.2" }],
        "label": ["calc(11px * var(--font-scale, 1))", { lineHeight: "1.2" }],
        "xs":  ["calc(0.75rem * var(--font-scale, 1))",  { lineHeight: "1rem" }],
        "node": ["calc(13px * var(--font-scale, 1))", { lineHeight: "1.25" }],
        "sm":  ["calc(0.875rem * var(--font-scale, 1))", { lineHeight: "1.25rem" }],
        "base": ["calc(1rem * var(--font-scale, 1))",    { lineHeight: "1.5rem" }],
        "lg":  ["calc(1.125rem * var(--font-scale, 1))", { lineHeight: "1.75rem" }],
        "xl":  ["calc(1.25rem * var(--font-scale, 1))",  { lineHeight: "1.75rem" }],
        "2xl": ["calc(1.5rem * var(--font-scale, 1))",   { lineHeight: "2rem" }],
        "3xl": ["calc(1.875rem * var(--font-scale, 1))", { lineHeight: "2.25rem" }],
      },
    },
  },
};
