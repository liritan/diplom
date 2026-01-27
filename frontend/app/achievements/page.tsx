"use client";

import { useEffect, useMemo, useState } from "react";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card } from "@/components/ui/common";

type AnalysisResult = { id: number };
type UserTestResult = { id: number };
type CaseSolution = { id: number };

type Achievement = {
  id: string;
  title: string;
  description: string;
  done: boolean;
};

export default function AchievementsPage() {
  const [analysisCount, setAnalysisCount] = useState(0);
  const [testsCount, setTestsCount] = useState(0);
  const [casesCount, setCasesCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const [a, t, c] = await Promise.all([
          api.get<AnalysisResult[]>("/analysis/me/results", { params: { limit: 1000 } }),
          api.get<UserTestResult[]>("/tests/me/results", { params: { limit: 1000 } }),
          api.get<CaseSolution[]>("/tests/me/case-solutions", { params: { limit: 1000 } }),
        ]);
        setAnalysisCount(a.data.length);
        setTestsCount(t.data.length);
        setCasesCount(c.data.length);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const achievements = useMemo<Achievement[]>(() => {
    return [
      {
        id: "a1",
        title: "Первый анализ",
        description: "Получите первый результат анализа навыков",
        done: analysisCount >= 1,
      },
      {
        id: "a2",
        title: "Три анализа",
        description: "Наберите 3 результата анализа (нужно для плана развития)",
        done: analysisCount >= 3,
      },
      {
        id: "t1",
        title: "Первый тест",
        description: "Пройдите тест и отправьте результаты на анализ",
        done: testsCount >= 1,
      },
      {
        id: "c1",
        title: "Первый кейс/симуляция",
        description: "Отправьте решение кейса или симуляции на анализ",
        done: casesCount >= 1,
      },
      {
        id: "m1",
        title: "Системный прогресс",
        description: "Соберите 10 событий (тесты + кейсы)",
        done: testsCount + casesCount >= 10,
      },
    ];
  }, [analysisCount, testsCount, casesCount]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Достижения</h1>
          <p className="text-brown-600 text-sm mt-1">Ваш прогресс и этапы развития</p>
        </div>

        <div className="p-8 overflow-y-auto">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {achievements.map((a) => (
                <Card key={a.id} className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-lg font-bold text-brown-800">{a.title}</div>
                      <div className="text-brown-600 text-sm mt-2">{a.description}</div>
                    </div>
                    <div
                      className={`px-3 py-1 rounded-full text-xs font-bold border ${
                        a.done
                          ? "bg-beige-200 border-beige-300 text-brown-800"
                          : "bg-white border-beige-300 text-brown-600"
                      }`}
                    >
                      {a.done ? "Получено" : "В процессе"}
                    </div>
                  </div>
                </Card>
              ))}

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 lg:col-span-2">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                    <div className="text-brown-600 text-xs">Анализы</div>
                    <div className="text-3xl font-bold text-brown-800 mt-2">{analysisCount}</div>
                  </div>
                  <div className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                    <div className="text-brown-600 text-xs">Тесты</div>
                    <div className="text-3xl font-bold text-brown-800 mt-2">{testsCount}</div>
                  </div>
                  <div className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                    <div className="text-brown-600 text-xs">Кейсы/симуляции</div>
                    <div className="text-3xl font-bold text-brown-800 mt-2">{casesCount}</div>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
