import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#05070d",
        night: "#0a0f1c",
        star: "#e8f1ff",
        ember: "#f4c26b",
        aurora: "#7cd7ff",
        lockedGray: "#3a4152",
      },
      fontFamily: {
        display: ['"Cinzel"', "ui-serif", "Georgia", "serif"],
        body: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(124, 215, 255, 0.35), 0 0 40px rgba(124, 215, 255, 0.15)",
        emberGlow: "0 0 20px rgba(244, 194, 107, 0.5), 0 0 60px rgba(244, 194, 107, 0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
