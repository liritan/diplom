import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-b from-blue-50 to-white text-center px-4">
      <h1 className="text-5xl font-extrabold text-blue-900 mb-6">Платформа развития soft skills</h1>
      <p className="text-xl text-gray-600 max-w-2xl mb-10">
        Развивайте коммуникацию, лидерство и эмоциональный интеллект через AI‑симуляции и аналитику прогресса.
      </p>
      
      <div className="space-x-4">
        <Link href="/login" className="px-8 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition">
          Начать
        </Link>
        <Link href="/login" className="px-8 py-3 bg-white text-blue-600 border border-blue-600 rounded-lg font-semibold hover:bg-blue-50 transition">
          Войти
        </Link>
      </div>
    </div>
  );
}
