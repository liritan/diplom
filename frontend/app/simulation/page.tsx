"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card, Button } from "@/components/ui/common";

type Test = {
  id: number;
  title: string;
  description: string;
  type: string;
  created_at: string;
};

type ActivePlan = {
  final_stage?: {
    final_test_id?: number | null;
    final_simulation_id?: number | null;
  } | null;
} | null;

type BaseScenario = {
  id: string;
  title: string;
  description: string;
  href: string;
};

function isFinalItem(test: Test, finalIds: Set<number>) {
  const title = String(test.title || "").toLowerCase();
  const description = String(test.description || "").toLowerCase();
  const text = `${title} ${description}`;
  return (
    finalIds.has(Number(test.id)) ||
    text.includes("[final]") ||
    text.includes("финальн") ||
    text.includes("итогов")
  );
}

export default function SimulationsPage() {
  const [tests, setTests] = useState<Test[]>([]);
  const [finalItemIds, setFinalItemIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const [testsRes, planRes] = await Promise.allSettled([
          api.get<Test[]>("/tests", { params: { limit: 300 } }),
          api.get<ActivePlan>("/plans/me/active"),
        ]);

        if (testsRes.status === "fulfilled") {
          setTests(Array.isArray(testsRes.value.data) ? testsRes.value.data : []);
        }

        if (planRes.status === "fulfilled") {
          const finalStage = planRes.value.data?.final_stage;
          const ids = [
            Number(finalStage?.final_test_id || 0),
            Number(finalStage?.final_simulation_id || 0),
          ].filter((id) => Number.isFinite(id) && id > 0);
          setFinalItemIds(ids);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    run();
  }, []);

  const finalIdSet = useMemo(() => new Set(finalItemIds), [finalItemIds]);
  const simulations = useMemo(
    () => tests.filter((t) => String(t.type).toLowerCase() === "simulation" && !isFinalItem(t, finalIdSet)),
    [tests, finalIdSet]
  );

  const baseScenarios = useMemo<BaseScenario[]>(
    () => [
      {
        id: "interview",
        title: "Собеседование",
        description: "Тренировка ответов на вопросы интервьюера.",
        href: "/simulation/interview",
      },
      {
        id: "conflict",
        title: "Конфликт в команде",
        description: "Практика сложных разговоров и снятия напряжения.",
        href: "/simulation/conflict",
      },
      {
        id: "negotiation",
        title: "Переговоры",
        description: "Тренировка аргументации и поиска договоренностей.",
        href: "/simulation/negotiation",
      },
      {
        id: "time-management",
        title: "Тайм-менеджмент",
        description: "Приоритизация задач и управление сроками.",
        href: "/simulation/time-management",
      },
      {
        id: "leadership",
        title: "Лидерство",
        description: "Ролевая практика управления командой и ответственностью.",
        href: "/simulation/leadership",
      },
    ],
    []
  );

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Ролевые игры</h1>
          <p className="text-brown-600 text-sm mt-1">
            Выберите симуляцию и потренируйтесь в формате чата
          </p>
        </div>

        <div className="p-8 overflow-y-auto space-y-8">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <>
              <div>
                <div className="text-sm font-bold text-brown-800 mb-3">Базовые сценарии</div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {baseScenarios.map((scenario) => (
                    <Card key={scenario.id} className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="inline-flex items-center px-3 py-1 rounded-full bg-beige-200 border border-beige-300 text-xs font-bold text-brown-800">
                            Сценарий
                          </div>
                          <h3 className="text-lg font-bold text-brown-800 mt-3">{scenario.title}</h3>
                          <p className="text-brown-600 text-sm mt-2">{scenario.description}</p>
                        </div>
                        <Link href={scenario.href}>
                          <Button className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider transition-colors">
                            Начать
                          </Button>
                        </Link>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-sm font-bold text-brown-800 mb-3">Все созданные симуляции</div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {simulations.map((t) => (
                    <Card key={t.id} className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="inline-flex items-center px-3 py-1 rounded-full bg-beige-200 border border-beige-300 text-xs font-bold text-brown-800">
                            Симуляция
                          </div>
                          <h3 className="text-lg font-bold text-brown-800 mt-3">{t.title}</h3>
                          <p className="text-brown-600 text-sm mt-2">{t.description}</p>
                        </div>
                        <Link href={`/simulation/${t.id}`}>
                          <Button className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider transition-colors">
                            Начать
                          </Button>
                        </Link>
                      </div>
                    </Card>
                  ))}

                  {!simulations.length ? (
                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <div className="text-brown-800 font-bold">Пока нет симуляций</div>
                      <div className="text-brown-600 text-sm mt-2">
                        Добавьте симуляции через админку (тип: simulation).
                      </div>
                    </Card>
                  ) : null}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
