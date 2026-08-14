import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        graphite: {
          950: "#0e0f11",
          900: "#15171a",
          800: "#1d2024",
          700: "#282c31",
          600: "#3a3f46",
          500: "#565d66",
          400: "#7c848d",
          300: "#a7aeb5",
          200: "#d3d7db",
          100: "#eceef0",
        },
        amber: {
          600: "#c9781f",
          500: "#e08e2b",
          400: "#f2a53d",
          300: "#f7c471",
        },
        signal: {
          green: "#4f9d69",
          red: "#c4574a",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      backgroundImage: {
        "diagonal-hatch":
          "repeating-linear-gradient(135deg, rgba(255,255,255,0.03) 0px, rgba(255,255,255,0.03) 1px, transparent 1px, transparent 10px)",
      },
    },
  },
  plugins: [],
};

export default config;
