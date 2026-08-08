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
      opacity: {
        8: '0.08',
        12: '0.12',
        14: '0.14',
        16: '0.16',
        18: '0.18',
        22: '0.22',
        26: '0.26',
        28: '0.28',
        42: '0.42',
        48: '0.48',
        52: '0.52',
        56: '0.56',
        58: '0.58',
        62: '0.62',
        68: '0.68',
        72: '0.72',
        78: '0.78',
        82: '0.82',
        84: '0.84',
        86: '0.86',
        88: '0.88',
        92: '0.92',
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        "destructive-muted": "hsl(var(--error-muted))",
        surface: "hsl(var(--surface))",
        "surface-raised": "hsl(var(--surface-raised))",
        success: "hsl(var(--success))",
        "success-muted": "hsl(var(--success-muted))",
        warning: "hsl(var(--warning))",
        "warning-muted": "hsl(var(--warning-muted))",
        info: "hsl(var(--info))",
        "info-muted": "hsl(var(--info-muted))",
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
