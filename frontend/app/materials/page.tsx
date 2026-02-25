"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

type MaterialProgress = {
  material_id: string;
  linked_test_id?: number | null;
  article_opened: boolean;
  article_opened_at?: string | null;
  test_completed: boolean;
  test_completed_at?: string | null;
  percentage: number;
};

type FinalStage = {
  final_test_id?: number | null;
  final_simulation_id?: number | null;
  unlocked: boolean;
  final_test_completed: boolean;
  final_simulation_completed: boolean;
  completed: boolean;
  level_up_applied: boolean;
  completed_at?: string | null;
  achievement_title?: string | null;
};

type BlockAchievement = {
  id: string;
  title: string;
  achieved_at?: string | null;
};

type Plan = {
  id: number;
  user_id: number;
  generated_at: string;
  is_archived: boolean;
  weaknesses: string[];
  materials: PlanMaterial[];
  material_progress: MaterialProgress[];
  tasks: PlanTask[];
  recommended_tests: Array<{ test_id: number; title: string; reason: string }>;
  final_stage?: FinalStage | null;
  block_achievements?: BlockAchievement[];
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

function progressBarClass(percentage: number) {
  if (percentage >= 100) return "bg-green-600";
  if (percentage >= 50) return "bg-accent-gold";
  return "bg-beige-300";
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error !== null) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

export default function MaterialsPage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [advancingLevel, setAdvancingLevel] = useState(false);
  const reloadTimerIds = useRef<number[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/plans/me/active");
      setPlan(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const scheduleLoad = useCallback(
    (delayMs: number) => {
      const timerId = window.setTimeout(() => {
        reloadTimerIds.current = reloadTimerIds.current.filter((id) => id !== timerId);
        load().catch(() => undefined);
      }, delayMs);
      reloadTimerIds.current.push(timerId);
    },
    [load]
  );

  useEffect(() => {
    const run = async () => {
      try {
        await load();
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [load]);

  useEffect(() => {
    const onFocus = () => {
      load().catch(() => undefined);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        load().catch(() => undefined);
      }
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  useEffect(() => {
    return () => {
      for (const timerId of reloadTimerIds.current) {
        window.clearTimeout(timerId);
      }
      reloadTimerIds.current = [];
    };
  }, []);

  const completeTask = async (taskId: string) => {
    try {
      const res = await api.post(`/plans/me/tasks/${taskId}/complete`);
      setMessage(`Задание выполнено. Прогресс плана: ${res.data.plan_progress}%`);
      await load();
    } catch (e: unknown) {
      console.error(e);
      setMessage(apiErrorMessage(e, "Ошибка при отметке задания"));
    }
  };

  const openMaterialArticle = async (material: PlanMaterial) => {
    const url = normalizeExternalUrl(material.url);
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }

    try {
      const res = await api.post(`/plans/me/materials/${material.id}/article-open`);
      setMessage(
        `Материал: ${res.data.material_percentage}% выполнено. Общий прогресс: ${res.data.plan_progress}%`
      );
      await load();
    } catch (e: unknown) {
      console.error(e);
      setMessage(apiErrorMessage(e, "Ошибка при отметке материала"));
    }
  };

  const generatePlan = async () => {
    try {
      const res = await api.post("/plans/me/generate");
      setMessage(res.data.message || "Генерация плана запущена");
      scheduleLoad(2500);
    } catch (e: unknown) {
      console.error(e);
      setMessage(apiErrorMessage(e, "Ошибка при генерации плана"));
    }
  };

  const advanceToNextLevel = async () => {
    try {
      setAdvancingLevel(true);
      const res = await api.post("/plans/me/final-stage/advance");
      setMessage(res.data?.message || "Переход на следующий уровень выполнен");
      await load();
      scheduleLoad(5500);
    } catch (e: unknown) {
      console.error(e);
      setMessage(apiErrorMessage(e, "Ошибка перехода на следующий уровень"));
    } finally {
      setAdvancingLevel(false);
    }
  };

  const tasks = useMemo(() => plan?.tasks ?? [], [plan]);
  const materials = useMemo(() => plan?.materials ?? [], [plan]);
  const recommendedTests = useMemo(() => plan?.recommended_tests ?? [], [plan]);
  const materialProgressMap = useMemo(() => {
    const map = new Map<string, MaterialProgress>();
    for (const row of plan?.material_progress ?? []) {
      map.set(row.material_id, row);
    }
    return map;
  }, [plan]);
  const finalStage = plan?.final_stage ?? null;

  const groupedMaterials = useMemo(() => {
    const order = [
      "communication",
      "emotional_intelligence",
      "critical_thinking",
      "time_management",
      "leadership",
    ];
    const groups = new Map<string, PlanMaterial[]>();
    for (const material of materials) {
      const key = String(material.skill || "").toLowerCase();
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)?.push(material);
    }
    return [...groups.entries()].sort((a, b) => {
      const ai = order.indexOf(a[0]);
      const bi = order.indexOf(b[0]);
      if (ai === -1 && bi === -1) return a[0].localeCompare(b[0]);
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
  }, [materials]);

  const finalTestHref =
    finalStage?.final_test_id && finalStage.final_test_id > 0
      ? `/tests/${finalStage.final_test_id}`
      : "/tests";
  const finalSimulationHref =
    finalStage?.final_simulation_id && finalStage.final_simulation_id > 0
      ? `/simulation/${finalStage.final_simulation_id}`
      : "/simulation";

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Материалы</h1>
          <p className="text-brown-600 text-sm mt-1">
            Ваш персональный план развития: материалы, задания и рекомендации
          </p>
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
                <div className="bg-beige-200 border border-beige-300 rounded-xl px-6 py-4 text-brown-800">
                  {message}
                </div>
              ) : null}

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 lg:col-span-2">
                  <h3 className="text-lg font-bold text-brown-800">Материалы по блокам навыков</h3>
                  <div className="mt-4 space-y-6">
                    {groupedMaterials.map(([skill, skillMaterials]) => (
                      <div key={skill} className="bg-beige-100 border border-beige-300 rounded-xl p-4">
                        <div className="text-sm font-bold text-brown-800 mb-3">{skillLabel(skill)}</div>
                        <div className="space-y-3">
                          {skillMaterials.map((material) => {
                            const progress = materialProgressMap.get(material.id);
                            const materialPercent = Math.round(Number(progress?.percentage ?? 0));
                            const linkedTestId = progress?.linked_test_id ?? null;
                            const testHref = linkedTestId && linkedTestId > 0 ? `/tests/${linkedTestId}` : "/tests";

                            return (
                              <div
                                key={material.id}
                                className="group bg-white border border-beige-300 rounded-xl p-4 transition-colors hover:bg-beige-200"
                              >
                                <div className="flex items-start justify-between gap-4">
                                  <div>
                                    <div className="text-sm font-bold text-brown-800">{material.title}</div>
                                    <div className="text-xs text-brown-600 mt-1">
                                      {materialTypeLabel(material.type)} • {difficultyLabel(material.difficulty)}
                                    </div>
                                  </div>
                                  <div className="min-w-[72px] text-right">
                                    <div className="text-sm font-bold text-brown-800">{materialPercent}%</div>
                                    <div className="mt-2 h-2 bg-beige-200 border border-beige-300 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full ${progressBarClass(materialPercent)}`}
                                        style={{ width: `${materialPercent}%` }}
                                      />
                                    </div>
                                  </div>
                                </div>

                                <div className="mt-3 grid grid-cols-2 gap-2 md:max-h-0 md:opacity-0 md:overflow-hidden md:group-hover:max-h-24 md:group-hover:opacity-100 transition-all">
                                  <Link href={testHref}>
                                    <Button className="w-full bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider">
                                      Тест
                                    </Button>
                                  </Link>
                                  <Button
                                    onClick={() => openMaterialArticle(material)}
                                    className="w-full bg-white hover:bg-beige-200 text-brown-800 border border-beige-300 font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider"
                                  >
                                    {materialTypeLabel(material.type)}
                                  </Button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}

                    {!materials.length ? (
                      <div className="text-brown-600 text-sm">Материалы пока не сформированы</div>
                    ) : null}
                  </div>

                  {finalStage?.unlocked ? (
                    <div className="mt-6 bg-beige-100 border border-beige-300 rounded-xl p-4">
                      <div className="text-sm font-bold text-brown-800">Финальные задания блока</div>
                      <div className="text-xs text-brown-600 mt-1">
                        После прохождения обоих заданий нажмите кнопку перехода на следующий уровень.
                      </div>

                      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                        <Link href={finalTestHref}>
                          <Button className="w-full bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider">
                            Финальный тест
                          </Button>
                        </Link>
                        <Link href={finalSimulationHref}>
                          <Button className="w-full bg-white hover:bg-beige-200 text-brown-800 border border-beige-300 font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider">
                            Финальное устное задание
                          </Button>
                        </Link>
                      </div>

                      <div className="mt-3 text-xs text-brown-700">
                        Тест: {finalStage.final_test_completed ? "пройден" : "в процессе"} • Ролевая игра:{" "}
                        {finalStage.final_simulation_completed ? "пройдена" : "в процессе"}
                      </div>
                      {finalStage.completed && !finalStage.level_up_applied ? (
                        <div className="mt-3">
                          <Button
                            onClick={advanceToNextLevel}
                            disabled={advancingLevel}
                            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider"
                          >
                            {advancingLevel ? "Переход..." : "Перейти на следующий уровень"}
                          </Button>
                        </div>
                      ) : null}
                      {finalStage.level_up_applied ? (
                        <div className="mt-2 text-xs font-bold text-green-700">
                          Уровень повышен. {finalStage.achievement_title || "Блок завершен"}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </Card>

                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800">Прогресс</h3>
                  <div className="mt-4">
                    <div className="text-brown-600 text-sm">
                      Выполнено: <span className="font-bold text-brown-800">{plan.progress.completed}</span> /{" "}
                      {plan.progress.total}
                    </div>
                    <div className="mt-3 bg-beige-200 border border-beige-300 rounded-full h-3 overflow-hidden">
                      <div className="bg-accent-gold h-full" style={{ width: `${plan.progress.percentage}%` }} />
                    </div>
                    <div className="mt-2 text-xs text-brown-600">{plan.progress.percentage}%</div>
                  </div>

                  <div className="mt-6">
                    <div className="text-sm font-bold text-brown-800">Зоны роста</div>
                    <div className="mt-3 space-y-2">
                      {(plan.weaknesses ?? []).map((w) => (
                        <div
                          key={w}
                          className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800 text-sm"
                        >
                          {w}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6">
                    <div className="text-sm font-bold text-brown-800">Достижения блока</div>
                    <div className="mt-3 space-y-2">
                      {(plan.block_achievements ?? []).length ? (
                        (plan.block_achievements ?? []).map((a) => (
                          <div
                            key={a.id}
                            className="bg-white border border-beige-300 rounded-lg px-4 py-3 text-brown-800 text-sm"
                          >
                            {a.title}
                          </div>
                        ))
                      ) : (
                        <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-600 text-sm">
                          Пока достижений нет — завершите финальные задания текущего блока.
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              </div>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800">Задания</h3>
                <div className="mt-4 space-y-3">
                  {tasks.map((t) => (
                    <div
                      key={t.id}
                      className="bg-beige-100 border border-beige-300 rounded-xl p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
                    >
                      <div>
                        <div className="text-brown-800 font-bold">{t.description}</div>
                        <div className="text-brown-600 text-xs mt-1">{skillLabel(t.skill)}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div
                          className={`text-xs font-bold ${t.status === "completed" ? "text-green-700" : "text-brown-800"}`}
                        >
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
                  {!tasks.length ? <div className="text-brown-600 text-sm">Задания пока не сформированы</div> : null}
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
              <p className="text-brown-600 text-sm mt-2">
                Сначала пройдите несколько анализов (чат/тесты), затем запустите генерацию плана.
              </p>
              {message ? (
                <div className="mt-4 bg-beige-100 border border-beige-300 rounded-xl px-6 py-4 text-brown-800">
                  {message}
                </div>
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

