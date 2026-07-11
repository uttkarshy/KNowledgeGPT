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
          950: "#12151B",
          900: "#171B22",
          800: "#1C212B",
          700: "#2A2E35",
          500: "#565C66",
          300: "#9AA0AB",
        },
        mist: {
          50: "#EDEFF2",
          100: "#E2E5EA",
          200: "#D3D7DE",
        },
        stamp: {
          teal: "#146661",
          tealLight: "#1C8983",
          tealDark: "#0E4A46",
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
    },
  },
  plugins: [],
};
