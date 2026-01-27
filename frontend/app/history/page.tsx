"use client";

import { useEffect, useMemo, useState } from "react";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card } from "@/components/ui/common";

type AnalysisResult = {
  id: number;
  task_id: string;
  created_at: string;
  feedback?: string | null;
  communication_score: number;
  emotional_intelligence_score: number;
  critical_thinking_score: number;
  time_management_score: number;
  leadership_score: number;
};

type UserTestResult = {
  id: number;
  test_id: number;
  completed_at: string;
  score?: number | null;
  ai_analysis?: string | null;
};

type CaseSolution = {
  id: number;
  test_id: number;
  solution: string;
  analysis_task_id?: string | null;
  created_at: string;
};

type TimelineItem =
  | { kind: "analysis"; date: string; data: AnalysisResult }
  | { kind: "test"; date: string; data: UserTestResult }
  | { kind: "case"; date: string; data: CaseSolution };

function formatDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const [analysis, setAnalysis] = useState<AnalysisResult[]>([]);
  const [tests, setTests] = useState<UserTestResult[]>([]);
  const [cases, setCases] = useState<CaseSolution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const [a, t, c] = await Promise.all([
          api.get("/analysis/me/results", { params: { limit: 100 } }),
          api.get("/tests/me/results", { params: { limit: 100 } }),
          api.get("/tests/me/case-solutions", { params: { limit: 100 } }),
        ]);
        setAnalysis(a.data);
        setTests(t.data);
        setCases(c.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const items = useMemo<TimelineItem[]>(() => {
    const a: TimelineItem[] = analysis.map((x) => ({ kind: "analysis", date: x.created_at, data: x }));
    const t: TimelineItem[] = tests.map((x) => ({ kind: "test", date: x.completed_at, data: x }));
    const c: TimelineItem[] = cases.map((x) => ({ kind: "case", date: x.created_at, data: x }));
    return [...a, ...t, ...c].sort((l, r) => new Date(r.date).getTime() - new Date(l.date).getTime());
  }, [analysis, tests, cases]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">История</h1>
          <p className="text-brown-600 text-sm mt-1">Все ваши анализы, тесты и решения кейсов в одном месте</p>
        </div>

        <div className="p-8 overflow-y-auto">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
              <h3 className="text-lg font-bold text-brown-800 mb-6">Лента активности</h3>
              {items.length ? (
                <div className="space-y-4">
                  {items.map((item, idx) => (
                    <div key={`${item.kind}-${idx}`} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                        <div className="text-sm font-bold text-brown-800">
                          {item.kind === "analysis" ? "Анализ" : item.kind === "test" ? "Тест" : "Кейс/симуляция"}
                        </div>
                        <div className="text-xs text-brown-600">{formatDate(item.date)}</div>
                      </div>

                      {item.kind === "analysis" ? (
                        <div className="mt-3 text-sm text-brown-800 whitespace-pre-wrap">{item.data.feedback || ""}</div>
                      ) : null}

                      {item.kind === "test" ? (
                        <div className="mt-3 text-sm text-brown-800 whitespace-pre-wrap">{item.data.ai_analysis || ""}</div>
                      ) : null}

                      {item.kind === "case" ? (
                        <div className="mt-3 text-sm text-brown-800 whitespace-pre-wrap">{item.data.solution}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-brown-600 text-sm">Пока нет событий</div>
              )}
            </Card>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
