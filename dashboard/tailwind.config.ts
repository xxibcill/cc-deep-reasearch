import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      spacing: {
        'page-x': 'clamp(1rem, 2.4vw, 2rem)',
        'page-y': 'clamp(1.5rem, 3vw, 2.5rem)',
        section: 'clamp(1.5rem, 2.4vw, 2.5rem)',
      },
      maxWidth: {
        content: '88rem',
      },
      boxShadow: {
        card: '0 18px 40px rgb(1 13 16 / 0.24), inset 0 1px 0 rgb(255 255 255 / 0.03)',
        'card-raised': '0 28px 60px rgb(1 13 16 / 0.38), inset 0 1px 0 rgb(255 255 255 / 0.04)',
        'card-flat': 'none',
        panel: '0 28px 65px rgb(1 13 16 / 0.38), inset 0 1px 0 rgb(255 255 255 / 0.04)',
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        surface: "hsl(var(--surface))",
        "surface-raised": "hsl(var(--surface-raised))",
        success: "hsl(var(--success))",
        "success-muted": "hsl(var(--success-muted))",
        warning: "hsl(var(--warning))",
        "warning-muted": "hsl(var(--warning-muted))",
        error: "hsl(var(--error))",
        "error-muted": "hsl(var(--error-muted))",
      },
      fontFamily: {
        display: ['"Barlow Condensed"', '"Arial Narrow"', 'sans-serif'],
        body: ['"IBM Plex Sans"', '"Segoe UI"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', '"SFMono-Regular"', 'monospace'],
      },
      keyframes: {
        'stage-pulse': {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
      animation: {
        'stage-pulse': 'stage-pulse 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
export default config
