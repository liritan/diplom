"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card, Button } from "@/components/ui/common";

type PlanTask = {
  id: string;
  description: string;
  skill: string;
  status: string;
  completed_at?: string | null;
};

type PlanMaterial = {
  id: string;
  title: string;
  url: string;
  type: string;
  skill: string;
  difficulty: string;
};

type Plan = {
  id: number;
  user_id: number;
  generated_at: string;
  is_archived: boolean;
  weaknesses: string[];
  materials: PlanMaterial[];
  tasks: PlanTask[];
  recommended_tests: Array<{ test_id: number; title: string; reason: string }>;
  progress: { completed: number; total: number; percentage: number };
};

function skillLabel(value: string) {
  const v = String(value || "").toLowerCase();
  if (v === "communication") return "Коммуникация";
  if (v === "emotional_intelligence") return "Эмоциональный интеллект";
  if (v === "critical_thinking") return "Критическое мышление";
  if (v === "time_management") return "Тайм-менеджмент";
  if (v === "leadership") return "Лидерство";
  return value;
}

function difficultyLabel(value: string) {
  const v = String(value || "").toLowerCase();
  if (v === "beginner") return "Начинающий";
  if (v === "intermediate") return "Средний";
  if (v === "advanced") return "Продвинутый";
  return value;
}

function materialTypeLabel(value: string) {
  const v = String(value || "").toLowerCase();
  if (v === "article") return "Статья";
  if (v === "video") return "Видео";
  if (v === "course") return "Курс";
  return value;
}

function normalizeExternalUrl(raw: string) {
  const url = String(raw || "").trim();
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("//")) return `https:${url}`;
  if (url.startsWith("/")) return url;
  return `https://${url}`;
}

export default function MaterialsPage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await api.get("/plans/me/active");
      setPlan(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    const run = async () => {
      try {
        await load();
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const completeTask = async (taskId: string) => {
    try {
      const res = await api.post(`/plans/me/tasks/${taskId}/complete`);
      setMessage(`Задание выполнено. Прогресс плана: ${res.data.plan_progress}%`);
      await load();
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка при отметке задания");
    }
  };

  const generatePlan = async () => {
    try {
      const res = await api.post("/plans/me/generate");
      setMessage(res.data.message || "Генерация плана запущена");
      setTimeout(() => {
        load().catch(() => undefined);
      }, 2500);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка при генерации плана");
    }
  };

  const tasks = useMemo(() => plan?.tasks ?? [], [plan]);
  const materials = useMemo(() => plan?.materials ?? [], [plan]);
  const recommendedTests = useMemo(() => plan?.recommended_tests ?? [], [plan]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Материалы</h1>
          <p className="text-brown-600 text-sm mt-1">Ваш персональный план развития: материалы, задания и рекомендации</p>
          <div className="mt-4">
            <Link href="/materials/library">
              <Button className="bg-white hover:bg-beige-200 text-brown-800 border border-beige-300 font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider">
                Каталог материалов и заданий
              </Button>
            </Link>
          </div>
        </div>

        <div className="p-8 overflow-y-auto space-y-8">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : plan ? (
            <>
              {message ? (
                <div className="bg-beige-200 border border-beige-300 rounded-xl px-6 py-4 text-brown-800">{message}</div>
              ) : null}

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 lg:col-span-2">
                  <h3 className="text-lg font-bold text-brown-800">Материалы</h3>
                  <div className="mt-4 space-y-3">
                    {materials.map((m) => (
                      <a
                        key={m.id}
                        href={normalizeExternalUrl(m.url)}
                        target="_blank"
                        rel="noreferrer"
                        className="block bg-beige-100 border border-beige-300 rounded-xl p-5 hover:bg-beige-200 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-sm font-bold text-brown-800">{m.title}</div>
                            <div className="text-xs text-brown-600 mt-1">{materialTypeLabel(m.type)} • {skillLabel(m.skill)} • {difficultyLabel(m.difficulty)}</div>
                          </div>
                          <div className="text-xs font-bold text-brown-800">Открыть</div>
                        </div>
                      </a>
                    ))}
                    {!materials.length ? (
                      <div className="text-brown-600 text-sm">Материалы пока не сформированы</div>
                    ) : null}
                  </div>
                </Card>

                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800">Прогресс</h3>
                  <div className="mt-4">
                    <div className="text-brown-600 text-sm">Выполнено: <span className="font-bold text-brown-800">{plan.progress.completed}</span> / {plan.progress.total}</div>
                    <div className="mt-3 bg-beige-200 border border-beige-300 rounded-full h-3 overflow-hidden">
                      <div className="bg-accent-gold h-full" style={{ width: `${plan.progress.percentage}%` }} />
                    </div>
                    <div className="mt-2 text-xs text-brown-600">{plan.progress.percentage}%</div>
                  </div>

                  <div className="mt-6">
                    <div className="text-sm font-bold text-brown-800">Зоны роста</div>
                    <div className="mt-3 space-y-2">
                      {(plan.weaknesses ?? []).map((w) => (
                        <div key={w} className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800 text-sm">{w}</div>
                      ))}
                    </div>
                  </div>
                </Card>
              </div>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800">Задания</h3>
                <div className="mt-4 space-y-3">
                  {tasks.map((t) => (
                    <div key={t.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div>
                        <div className="text-brown-800 font-bold">{t.description}</div>
                        <div className="text-brown-600 text-xs mt-1">{skillLabel(t.skill)}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className={`text-xs font-bold ${t.status === "completed" ? "text-green-700" : "text-brown-800"}`}>
                          {t.status === "completed" ? "Выполнено" : "В процессе"}
                        </div>
                        {t.status !== "completed" ? (
                          <Button
                            onClick={() => completeTask(t.id)}
                            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                          >
                            Выполнить
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  {!tasks.length ? (
                    <div className="text-brown-600 text-sm">Задания пока не сформированы</div>
                  ) : null}
                </div>
              </Card>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800">Рекомендованные тесты</h3>
                <div className="mt-4 space-y-3">
                  {recommendedTests.map((rt) => (
                    <a
                      key={rt.test_id}
                      href={rt.test_id && rt.test_id > 0 ? `/tests/${rt.test_id}` : "/tests"}
                      className="block bg-beige-100 border border-beige-300 rounded-xl p-5 hover:bg-beige-200 transition-colors"
                    >
                      <div className="text-sm font-bold text-brown-800">{rt.title}</div>
                      <div className="text-xs text-brown-600 mt-2">{rt.reason}</div>
                    </a>
                  ))}
                  {!recommendedTests.length ? (
                    <div className="text-brown-600 text-sm">Рекомендации пока не сформированы</div>
                  ) : null}
                </div>
              </Card>
            </>
          ) : (
            <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
              <h3 className="text-lg font-bold text-brown-800">План развития пока не создан</h3>
              <p className="text-brown-600 text-sm mt-2">Сначала пройдите несколько анализов (чат/тесты), затем запустите генерацию плана.</p>
              {message ? (
                <div className="mt-4 bg-beige-100 border border-beige-300 rounded-xl px-6 py-4 text-brown-800">{message}</div>
              ) : null}
              <div className="mt-6">
                <Button
                  onClick={generatePlan}
                  className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                >
                  Сгенерировать план
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
