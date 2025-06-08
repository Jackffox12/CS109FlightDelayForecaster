/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html','./src/**/*.{js,ts,jsx,tsx}'],
  safelist: [
    'fixed','bottom-0','inset-x-0','z-50',
    'h-[40vh]','md:h-[30vh]',
    'bg-white/15','backdrop-blur-lg',
    'rounded-t-2xl','px-6','py-4','text-white'
  ],
  theme: {
    fontFamily:{ sans:['Inter','ui-sans-serif','system-ui'] },
    extend:{ 
      colors:{ 
        brand:'#111',
        text: {
          DEFAULT: '#ffffff'
        }
      }
    }
  },
  plugins: [],
} 