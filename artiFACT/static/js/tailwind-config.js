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
    },
  },
};
