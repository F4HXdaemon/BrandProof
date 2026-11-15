import type { Config } from "tailwindcss";

/**
 * BrandProof design tokens
 * Warm off-white paper, ink text, one milky-orange accent.
 * Status colours are deliberately muted so they read as information, not decoration.
 */
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#FAF7F2", // page background (off-white)
        surface: "#FFFEFB", // cards, inputs
        sunken: "#F3EEE5", // inset panels, hover fills
        line: {
          DEFAULT: "#E9E2D6", // hairlines
          strong: "#D8CFBF", // input borders, emphasised rules
        },
        ink: {
          DEFAULT: "#2B2622",
          soft: "#5F574D",
          mute: "#766D61",
        },
        accent: {
          DEFAULT: "#EDA06F", // milky orange: fills, buttons
          hover: "#E58F58",
          soft: "#FBEBDD", // tinted background
          ink: "#A34A14", // orange used as text / links (AA on paper)
        },
        // Muted status palette (remaps the Tailwind scales the app already uses)
        emerald: { 300: "#3F7352", 400: "#3F7352", 500: "#4E7F5F", 600: "#3F7352", 900: "#DCE9DF", 950: "#EEF4EF" },
        rose: { 100: "#7A2E22", 200: "#8A3426", 300: "#9C3B2B", 400: "#A8402F", 500: "#C2573F", 600: "#B34A33", 950: "#F8E9E4" },
        amber: { 100: "#6B4710", 200: "#76500F", 300: "#8A5C0F", 400: "#93610F", 500: "#B07A1F", 600: "#9A6612", 950: "#FAF1DE" },
        yellow: { 300: "#7A6212", 400: "#80670F", 500: "#B89A2A", 950: "#FAF3D8" },
        orange: { 400: "#A8531C", 500: "#D9763A" },
        sky: { 300: "#3E6A80", 400: "#3E6A80", 500: "#5A8AA0", 600: "#3E6A80" },
        blue: { 400: "#46628A", 500: "#6482AA" },
        cyan: { 300: "#3E6A80", 400: "#3E6A80" },
        purple: { 300: "#6B4F86", 400: "#6B4F86", 500: "#8B6FA6" },
      },
      fontFamily: {
        sans: ['"Instrument Sans Variable"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        serif: ['"Newsreader Variable"', "ui-serif", "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 10px 30px -12px rgba(70, 45, 20, 0.18)",
      },
    },
  },
  plugins: [],
};
export default config;
