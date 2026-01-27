import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        beige: {
          100: '#fbf8f3',
          200: '#f5efe6',
          300: '#e6dfd5',
        },
        brown: {
          400: '#d4c5b0',
          600: '#a69076',
          800: '#5c4d3c',
        },
        accent: {
          gold: '#e2c08d',
          button: '#d2c4b0',
          buttonHover: '#c1b098',
        }
      },
    },
  },
  plugins: [],
};
export default config;
