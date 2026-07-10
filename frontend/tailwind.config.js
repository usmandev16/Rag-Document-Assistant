module.exports = {
  content: ["./src/Homepage.jsx", "./src/TechnicalOverview.jsx"],
  corePlugins: {
    // Preflight resets bare tag styles (button, h1, etc.) globally, which
    // would bleed into the existing chat app's CSS since nothing here is
    // component-scoped. Off, so Homepage's utility classes work without
    // touching anything outside itself.
    preflight: false,
  },
  theme: {
    extend: {
      // Light theme: neutral off-white background so the mint accent
      // stays an accent (buttons, chips, icons) instead of washing the
      // whole page.
      colors: {
        paper: "#F7F8F7",
        surface: "#FFFFFF",
        ink: "#1A1D1F",
        muted: "#6B7280",
        faint: "#9CA3AF",
        rule: "rgba(0,0,0,0.08)",
        coral: {
          50: "#E3F6EF",
          100: "#CDEFE3",
          200: "#9FE0C9",
          400: "#3FD1AA",
          500: "#23C69E",
          600: "#10A37F",
        },
        sage: {
          50: "#E9F5F1",
          100: "#D6EEE6",
          200: "#AEDDCC",
          500: "#10A37F",
          600: "#0C8567",
        },
      },
      fontFamily: {
        serif: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        "4xl": "28px",
        "5xl": "36px",
      },
    },
  },
  plugins: [],
};
