/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'navy': {
          900: '#0a0f1e',
          800: '#0f1729',
          700: '#151f36',
          600: '#1c2a4a',
        },
        'cyan': {
          400: '#00d4ff',
          500: '#00b8e6',
        },
        'success': '#00ff88',
        'danger': '#ff4444',
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
