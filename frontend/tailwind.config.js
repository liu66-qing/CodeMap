/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        pixel: ['"Press Start 2P"', 'monospace'],
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: { 50: '#eff6ff', 100: '#dbeafe', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
        graph: {
          person: '#3b82f6',
          organization: '#10b981',
          product: '#f59e0b',
          event: '#ef4444',
          location: '#8b5cf6',
          technology: '#06b6d4',
          concept: '#6b7280',
        },
      },
      animation: {
        'float-slow': 'float 8s ease-in-out infinite',
        'float-med': 'float 6s ease-in-out infinite 1s',
        'float-fast': 'float 4s ease-in-out infinite 2s',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0) translateX(0)' },
          '50%': { transform: 'translateY(-8px) translateX(4px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 4px rgba(99,102,241,0.3)' },
          '100%': { boxShadow: '0 0 12px rgba(99,102,241,0.6)' },
        },
      },
    },
  },
  plugins: [],
}
