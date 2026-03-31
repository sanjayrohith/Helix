/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'background': '#0a0f1e',
        'surface': '#0d1526',
        'primary': '#ffffff',
        'secondary': '#8892a4',
        'navy': {
          950: '#060b17',
          900: '#0a0f1e',
          800: '#0d1526',
          700: '#151f36',
          600: '#1c2a4a',
        },
        'cyan': {
          DEFAULT: '#00d4ff',
          400: '#00d4ff',
          500: '#00b8e6',
          600: '#0099bb',
        },
        'success': '#00ff88',
        'danger': '#ff4444',
        'amber': {
          400: '#ffb800',
        },
        'text': {
          primary: '#ffffff',
          secondary: '#8892a4',
          muted: '#3a4a5c',
          dim: '#2a3545',
        },
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'monospace'],
        'heading': ['Syne', 'sans-serif'],
      },
      borderRadius: {
        'card': '8px',
        'input': '6px',
      },
    },
  },
  plugins: [],
}
