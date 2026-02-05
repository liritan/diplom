"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Card, Button } from "@/components/ui/common";
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, Tooltip } from 'recharts';
import AppLayout from "@/components/AppLayout";
import { LogOut } from "lucide-react";

const round1 = (value: number) => Math.round(value * 10) / 10;

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [analysisCount, setAnalysisCount] = useState(0);
  const [testCount, setTestCount] = useState(0);
  const [planProgress, setPlanProgress] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(
    async (showLoading: boolean) => {
      if (!user) return;
      if (showLoading) setLoading(true);
      try {
        const [p, a, t, plan] = await Promise.all([
          api.get("/profiles/me"),
          api.get("/analysis/me/results", { params: { limit: 200 } }),
          api.get("/tests/me/results", { params: { limit: 200 } }),
          api.get("/plans/me/active"),
        ]);
        setProfile(p.data);
        setAnalysisCount(Array.isArray(a.data) ? a.data.length : 0);
        setTestCount(Array.isArray(t.data) ? t.data.length : 0);
        setPlanProgress(plan.data?.progress?.percentage ?? null);
      } catch (err) {
        console.error(err);
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [user]
  );

  useEffect(() => {
    if (!user) return;

    let disposed = false;
    fetchStats(true);

    const interval = window.setInterval(() => {
      if (disposed) return;
      fetchStats(false);
    }, 15000);

    const onFocus = () => {
      if (disposed) return;
      fetchStats(false);
    };

    const onVisibilityChange = () => {
      if (disposed) return;
      if (document.visibilityState === "visible") {
        fetchStats(false);
      }
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      disposed = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [user, fetchStats]);

  const avgScore = profile
    ? (Number(profile.communication_score ?? 0)
        + Number(profile.emotional_intelligence_score ?? 0)
        + Number(profile.critical_thinking_score ?? 0)
        + Number(profile.time_management_score ?? 0)
        + Number(profile.leadership_score ?? 0)) / 5
    : 0;

  const avgScoreRounded = round1(avgScore);

  const level = avgScore >= 70 ? "Продвинутый" : avgScore >= 40 ? "Средний" : "Начинающий";

  const data = profile ? [
    { subject: 'Коммуникация', A: round1(profile.communication_score ?? 0), fullMark: 100 },
    { subject: 'Эмоциональный интеллект', A: round1(profile.emotional_intelligence_score ?? 0), fullMark: 100 },
    { subject: 'Критическое мышление', A: round1(profile.critical_thinking_score ?? 0), fullMark: 100 },
    { subject: 'Тайм-менеджмент', A: round1(profile.time_management_score ?? 0), fullMark: 100 },
    { subject: 'Лидерство', A: round1(profile.leadership_score ?? 0), fullMark: 100 },
  ] : [
    { subject: 'Коммуникация', A: 0, fullMark: 100 },
    { subject: 'Эмоциональный интеллект', A: 0, fullMark: 100 },
    { subject: 'Критическое мышление', A: 0, fullMark: 100 },
    { subject: 'Тайм-менеджмент', A: 0, fullMark: 100 },
    { subject: 'Лидерство', A: 0, fullMark: 100 },
  ];

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-brown-800">Статистика</h1>
            <p className="text-brown-600 text-sm mt-1">Отслеживайте свой прогресс и развитие навыков</p>
          </div>
          <Button onClick={logout} className="bg-transparent text-brown-600 border border-brown-400 hover:bg-beige-200">
            <LogOut className="w-4 h-4 mr-2" /> Выйти
          </Button>
        </div>

        <div className="p-8 overflow-y-auto">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <h3 className="text-lg font-bold text-brown-800 mb-6">Ваш профиль компетенций</h3>
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
                      <PolarGrid stroke="#e6dfd5" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#5c4d3c', fontSize: 12 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#d4c5b0" />
                      <Radar name="Мои навыки" dataKey="A" stroke="#a69076" fill="#d4c5b0" fillOpacity={0.6} />
                      <Tooltip contentStyle={{ backgroundColor: '#fbf8f3', borderColor: '#e6dfd5', color: '#5c4d3c' }} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 flex flex-col justify-center items-center text-center">
                <h3 className="text-lg font-bold text-brown-800 mb-4">Текущий уровень</h3>
                <div className="text-5xl font-bold text-accent-gold mb-2">{level}</div>
                <p className="text-brown-600 mb-8">Ваш средний уровень навыков: {avgScoreRounded}/100</p>

                <div className="w-full space-y-4">
                  <div className="flex justify-between text-sm text-brown-800">
                    <span>Анализов выполнено</span>
                    <span className="font-bold">{analysisCount}</span>
                  </div>
                  <div className="flex justify-between text-sm text-brown-800">
                    <span>Пройдено тестов</span>
                    <span className="font-bold">{testCount}</span>
                  </div>
                  <div className="flex justify-between text-sm text-brown-800">
                    <span>Прогресс плана</span>
                    <span className="font-bold">{planProgress === null ? "—" : `${planProgress}%`}</span>
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
