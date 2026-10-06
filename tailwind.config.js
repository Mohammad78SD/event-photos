/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/src/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        pearl: "#F7F5F2",
        paper: "#FDFCFA",
        card: "#FAF8F5",
        ink: "#1A1A1A",
        "ink-soft": "#46403A",
        muted: "#6B6560",
        "muted-2": "#8C857E",
        hairline: "#DCD6CE",
        border: "#E8E3DB",
        "border-2": "#CFC8BE",
        track: "#E6E1D9",
        "on-ink": "#FAF8F5",
      },
      fontFamily: {
        display: ["'Playfair Display'", "Vazirmatn", "serif"],
        script: ["'Pinyon Script'", "Vazirmatn", "cursive"],
        body: ["Vazirmatn", "sans-serif"],
      },
      borderRadius: {
        pill: "27px",
      },
    },
  },
  plugins: [],
};
