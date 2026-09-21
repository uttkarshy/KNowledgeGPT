/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // "Archive ledger" palette — deliberately not the cream+terracotta
        // or near-black+acid-green defaults. Ink/mist form the surfaces;
        // stamp-teal is the primary interactive color; highlight-amber is
        // reserved ONLY for citations/provenance, never for general UI,
        // so it stays meaningful as "this came from a source."
        ink: {
          950: "#101512",
          900: "#18201C",
          800: "#27312C",
          700: "#39443E",
          500: "#68736D",
          300: "#AAB2AD",
        },
        mist: {
          50: "#F0F2F0",
          100: "#E8EBE8",
          200: "#DCE1DD",
        },
        canvas: "#F8F9F7",
        stamp: {
          teal: "#176B5B",
          tealLight: "#46A08E",
          tealDark: "#105246",
        },
        highlight: {
          amber: "#D98E2B",
          amberLight: "#F0AC55",
          amberDark: "#A8681A",
        },
        success: "#5E8F6B",
        danger: "#B5493D",
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "ui-serif", "Georgia", "serif"],
        body: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        tab: "6px 6px 0 0", // the file-tab citation chip shape
        card: "16px",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(217,142,43,0.0)" },
          "30%": { boxShadow: "0 0 0 4px rgba(217,142,43,0.35)" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 900ms ease-out 1",
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,21,18,.04), 0 10px 28px rgba(16,21,18,.035)",
        float: "0 24px 60px rgba(16,21,18,.14)",
      },
    },
  },
  plugins: [],
};
