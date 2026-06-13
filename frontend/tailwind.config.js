/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        ink: {
          950: "#070b16",
          900: "#0a0f1f",
          850: "#0e1426",
          800: "#131a30",
          700: "#1b243f",
          600: "#27324f",
        },
        // semantic accents tied to the pipeline stages
        task: "#7dd3fc",
        agent: "#818cf8",
        run: "#38bdf8",
        bench: "#22d3ee",
        diagnose: "#c084fc",
        repair: "#34d399",
        memory: "#f0abfc",
        danger: "#fb7185",
        warn: "#fbbf24",
        good: "#34d399",
      },
      boxShadow: {
        glow: "0 0 40px -8px rgba(34,211,238,0.35)",
        "glow-rose": "0 0 40px -8px rgba(251,113,133,0.35)",
        "glow-emerald": "0 0 40px -8px rgba(52,211,153,0.35)",
        card: "0 8px 30px -12px rgba(0,0,0,0.6)",
      },
      keyframes: {
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        "pulse-ring": {
          "0%": { transform: "scale(0.8)", opacity: "0.7" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "spin-slow": "spin-slow 18s linear infinite",
        "pulse-ring": "pulse-ring 2.4s ease-out infinite",
        float: "float 5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
