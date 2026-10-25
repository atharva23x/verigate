/**
 * The palette steps this app actually uses are mapped to CSS variables so the
 * whole UI can flip between the dark (default) and light themes.
 *   :root            -> dark values  (src/index.css)
 *   [data-theme=...] -> light values (src/index.css)
 * Steps not listed here keep Tailwind's static defaults (solid fills only).
 */
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        slate: {
          100: v("--slate-100"),
          200: v("--slate-200"),
          300: v("--slate-300"),
          400: v("--slate-400"),
          500: v("--slate-500"),
          600: v("--slate-600"),
          700: v("--slate-700"),
          800: v("--slate-800"),
          900: v("--slate-900"),
          950: v("--slate-950"),
        },
        amber: {
          200: v("--amber-200"),
          300: v("--amber-300"),
          400: v("--amber-400"),
        },
        emerald: {
          200: v("--emerald-200"),
          300: v("--emerald-300"),
          400: v("--emerald-400"),
        },
        indigo: {
          200: v("--indigo-200"),
          300: v("--indigo-300"),
          400: v("--indigo-400"),
          950: v("--indigo-950"),
        },
        sky: {
          100: v("--sky-100"),
          200: v("--sky-200"),
          300: v("--sky-300"),
          400: v("--sky-400"),
        },
        rose: {
          200: v("--rose-200"),
          300: v("--rose-300"),
          400: v("--rose-400"),
        },
        orange: {
          300: v("--orange-300"),
          400: v("--orange-400"),
        },
        violet: {
          300: v("--violet-300"),
        },
        fuchsia: {
          300: v("--fuchsia-300"),
        },
      },
      keyframes: {
        pulsebox: {
          "0%, 100%": { boxShadow: "0 0 0 2px rgba(239,68,68,0.9)" },
          "50%": { boxShadow: "0 0 0 6px rgba(239,68,68,0.35)" },
        },
      },
      animation: {
        pulsebox: "pulsebox 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
