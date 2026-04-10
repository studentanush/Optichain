/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
      },
      colors: {
        surface: {
          DEFAULT: "#0f1419",
          raised: "#161d26",
          border: "#243041",
        },
        accent: {
          DEFAULT: "#3b82f6",
          muted: "#1e3a5f",
        },
        danger: "#f87171",
        warn: "#fbbf24",
        ok: "#34d399",
      },
    },
  },
  plugins: [],
};
