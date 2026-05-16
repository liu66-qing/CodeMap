/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
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
    },
  },
  plugins: [],
}
