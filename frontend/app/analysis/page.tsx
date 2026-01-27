"use client";

import { useEffect, useMemo, useState } from "react";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card } from "@/components/ui/common";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Legend,
} from "recharts";

type ProfileHistoryItem = {
  id: number;
  user_id: number;
  profile_id: number;
  communication_score: number;
  emotional_intelligence_score: number;
  critical_thinking_score: number;
  time_management_score: number;
  leadership_score: number;
  created_at: string;
};

type ProfileWithHistory = {
  current: Record<string, number>;
  history: ProfileHistoryItem[];
  strengths: string[];
  weaknesses: string[];
};

type AnalysisResult = {
  id: number;
  task_id: string;
  user_id: number;
  communication_score: number;
  emotional_intelligence_score: number;
  critical_thinking_score: number;
  time_management_score: number;
  leadership_score: number;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  feedback?: string | null;
  created_at: string;
};

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

export default function AnalysisPage() {
  const [profile, setProfile] = useState<ProfileWithHistory | null>(null);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const [p, r] = await Promise.all([
          api.get("/profiles/me/history", { params: { months: 6 } }),
          api.get("/analysis/me/results", { params: { limit: 20 } }),
        ]);
        setProfile(p.data);
        setResults(r.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    run();
  }, []);

  const radarData = useMemo(() => {
    const current = profile?.current;
    if (!current) return [];
    return [
      { subject: "Communication", A: current.communication_score ?? 0, fullMark: 100 },
      { subject: "Emotional Intelligence", A: current.emotional_intelligence_score ?? 0, fullMark: 100 },
      { subject: "Critical Thinking", A: current.critical_thinking_score ?? 0, fullMark: 100 },
      { subject: "Time Management", A: current.time_management_score ?? 0, fullMark: 100 },
      { subject: "Leadership", A: current.leadership_score ?? 0, fullMark: 100 },
    ];
  }, [profile]);

  const historyChartData = useMemo(() => {
    const history = profile?.history ?? [];
    return history
      .slice()
      .reverse()
      .map((h) => ({
        date: new Date(h.created_at).toLocaleDateString("ru-RU"),
        Communication: h.communication_score,
        "Emotional Intelligence": h.emotional_intelligence_score,
        "Critical Thinking": h.critical_thinking_score,
        "Time Management": h.time_management_score,
        Leadership: h.leadership_score,
      }));
  }, [profile]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Анализ навыков</h1>
          <p className="text-brown-600 text-sm mt-1">Ваши сильные и слабые стороны, динамика и последние результаты анализа</p>
        </div>

        <div className="p-8 overflow-y-auto">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <div className="space-y-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800 mb-6">Текущий профиль</h3>
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                        <PolarGrid stroke="#e6dfd5" />
                        <PolarAngleAxis dataKey="subject" tick={{ fill: "#5c4d3c", fontSize: 12 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#d4c5b0" />
                        <Radar name="Мои навыки" dataKey="A" stroke="#a69076" fill="#d4c5b0" fillOpacity={0.6} />
                        <Tooltip contentStyle={{ backgroundColor: "#fbf8f3", borderColor: "#e6dfd5", color: "#5c4d3c" }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800 mb-6">Сильные и слабые стороны</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <div className="text-sm font-bold text-brown-800 mb-3">Сильные стороны</div>
                      <div className="space-y-2">
                        {(profile?.strengths ?? []).length ? (
                          (profile?.strengths ?? []).map((s) => (
                            <div key={s} className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">
                              {s}
                            </div>
                          ))
                        ) : (
                          <div className="text-brown-600 text-sm">Пока недостаточно данных</div>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-brown-800 mb-3">Зоны роста</div>
                      <div className="space-y-2">
                        {(profile?.weaknesses ?? []).length ? (
                          (profile?.weaknesses ?? []).map((w) => (
                            <div key={w} className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">
                              {w}
                            </div>
                          ))
                        ) : (
                          <div className="text-brown-600 text-sm">Пока недостаточно данных</div>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              </div>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800 mb-6">Динамика (последние 6 месяцев)</h3>
                {historyChartData.length ? (
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={historyChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke="#e6dfd5" />
                        <XAxis dataKey="date" tick={{ fill: "#5c4d3c", fontSize: 12 }} />
                        <YAxis domain={[0, 100]} tick={{ fill: "#5c4d3c", fontSize: 12 }} />
                        <Tooltip contentStyle={{ backgroundColor: "#fbf8f3", borderColor: "#e6dfd5", color: "#5c4d3c" }} />
                        <Legend />
                        <Line type="monotone" dataKey="Communication" stroke="#a69076" dot={false} />
                        <Line type="monotone" dataKey="Emotional Intelligence" stroke="#e2c08d" dot={false} />
                        <Line type="monotone" dataKey="Critical Thinking" stroke="#5c4d3c" dot={false} />
                        <Line type="monotone" dataKey="Time Management" stroke="#d4c5b0" dot={false} />
                        <Line type="monotone" dataKey="Leadership" stroke="#c1b098" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="text-brown-600 text-sm">История пока пустая. Пройдите несколько тестов или попрактикуйтесь в чате.</div>
                )}
              </Card>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800 mb-6">Последние результаты анализа</h3>
                {results.length ? (
                  <div className="space-y-4">
                    {results.map((r) => (
                      <div key={r.id} className="border border-beige-300 rounded-xl p-5 bg-beige-100">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                          <div className="text-sm font-bold text-brown-800">{formatDate(r.created_at)}</div>
                          <div className="text-xs text-brown-600">Task: {r.task_id}</div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4 text-sm">
                          <div className="text-brown-800">Comm: <span className="font-bold">{Math.round(r.communication_score)}</span></div>
                          <div className="text-brown-800">EI: <span className="font-bold">{Math.round(r.emotional_intelligence_score)}</span></div>
                          <div className="text-brown-800">CT: <span className="font-bold">{Math.round(r.critical_thinking_score)}</span></div>
                          <div className="text-brown-800">TM: <span className="font-bold">{Math.round(r.time_management_score)}</span></div>
                          <div className="text-brown-800">Lead: <span className="font-bold">{Math.round(r.leadership_score)}</span></div>
                        </div>
                        {r.feedback ? (
                          <div className="mt-4 text-sm text-brown-800 whitespace-pre-wrap">{r.feedback}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-brown-600 text-sm">Пока нет результатов анализа</div>
                )}
              </Card>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
