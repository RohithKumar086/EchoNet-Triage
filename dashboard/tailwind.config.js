/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // EchoNet brand palette — derived from the logo
        echo: {
          dark:    '#060612',
          deeper:  '#0a0a1a',
          surface: '#0f0f24',
          card:    '#141430',
          border:  '#1e1e3f',
          muted:   '#4a4a7a',
        },
        teal: {
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
        },
        cyan: {
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
        },
        violet: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        fuchsia: {
          400: '#e879f9',
          500: '#d946ef',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow':   'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow':         'glow 2s ease-in-out infinite alternate',
        'slide-up':     'slideUp 0.4s ease-out',
        'fade-in':      'fadeIn 0.5s ease-out',
        'shimmer':      'shimmer 2.5s linear infinite',
      },
      keyframes: {
        glow: {
          '0%':   { opacity: '0.4' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #14b8a6, #06b6d4, #8b5cf6, #d946ef)',
        'gradient-card':  'linear-gradient(145deg, rgba(20,20,48,0.8), rgba(10,10,26,0.95))',
      },
      boxShadow: {
        'glow-teal':   '0 0 20px rgba(20, 184, 166, 0.3)',
        'glow-cyan':   '0 0 20px rgba(6, 182, 212, 0.3)',
        'glow-violet': '0 0 20px rgba(139, 92, 246, 0.3)',
      },
    },
  },
  plugins: [],
}
