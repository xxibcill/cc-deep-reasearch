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
        'page-x': '1rem',
        'page-y': '1.5rem',
        section: '1.5rem',
      },
      maxWidth: {
        content: '80rem',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(0 0 0 / 0.15)',
        'card-raised': '0 4px 6px -1px rgb(0 0 0 / 0.2), 0 2px 4px -2px rgb(0 0 0 / 0.15)',
        'card-flat': 'none',
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
        display: ['"Space Grotesk"', '"Segoe UI"', 'sans-serif'],
        body: ['"Source Sans 3"', '"Segoe UI"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', 'monospace'],
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
  plugins: [],
}
export default config
