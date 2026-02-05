"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card, Button } from "@/components/ui/common";

type LibraryMaterial = {
  plan_id: number;
  plan_generated_at: string;
  id: string;
  title: string;
  url: string;
  type: string;
  skill: string;
  difficulty: string;
};

type LibraryTask = {
  plan_id: number;
  plan_generated_at: string;
  id: string;
  description: string;
  skill: string;
  status: string;
  completed_at?: string | null;
};

type LibraryResponse = {
  materials: LibraryMaterial[];
  tasks: LibraryTask[];
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

export default function MaterialsLibraryPage() {
  const [data, setData] = useState<LibraryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await api.get<LibraryResponse>("/plans/me/library");
      setData(res.data);
    } catch (e) {
      console.error(e);
      setData({ materials: [], tasks: [] });
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

  const materials = useMemo(() => data?.materials ?? [], [data]);
  const tasks = useMemo(() => data?.tasks ?? [], [data]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brown-800">Каталог материалов и заданий</h1>
              <p className="text-brown-600 text-sm mt-1">
                Все материалы и задания из ваших планов развития (включая прошлые)
              </p>
            </div>
            <Link href="/materials">
              <Button className="bg-white hover:bg-beige-200 text-brown-800 border border-beige-300 font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider">
                Вернуться к активному плану
              </Button>
            </Link>
          </div>
        </div>

        <div className="p-8 overflow-y-auto space-y-8">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800">Материалы ({materials.length})</h3>
                  <div className="mt-4 space-y-3">
                    {materials.map((m) => (
                      <a
                        key={`${m.plan_id}:${m.id}`}
                        href={normalizeExternalUrl(m.url)}
                        target="_blank"
                        rel="noreferrer"
                        className="block bg-beige-100 border border-beige-300 rounded-xl p-5 hover:bg-beige-200 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-sm font-bold text-brown-800">{m.title}</div>
                            <div className="text-xs text-brown-600 mt-1">
                              {materialTypeLabel(m.type)} • {skillLabel(m.skill)} • {difficultyLabel(m.difficulty)}
                            </div>
                            <div className="text-xs text-brown-600 mt-2">План #{m.plan_id} • {formatDate(m.plan_generated_at)}</div>
                          </div>
                          <div className="text-xs font-bold text-brown-800">Открыть</div>
                        </div>
                      </a>
                    ))}
                    {!materials.length ? (
                      <div className="text-brown-600 text-sm">Материалов пока нет</div>
                    ) : null}
                  </div>
                </Card>

                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <h3 className="text-lg font-bold text-brown-800">Задания ({tasks.length})</h3>
                  <div className="mt-4 space-y-3">
                    {tasks.map((t) => (
                      <div key={`${t.plan_id}:${t.id}`} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-brown-800 font-bold">{t.description}</div>
                            <div className="text-brown-600 text-xs mt-1">{skillLabel(t.skill)}</div>
                            <div className="text-brown-600 text-xs mt-2">План #{t.plan_id} • {formatDate(t.plan_generated_at)}</div>
                          </div>
                          <div className={`text-xs font-bold ${t.status === "completed" ? "text-green-700" : "text-brown-800"}`}>
                            {t.status === "completed" ? "Выполнено" : "В процессе"}
                          </div>
                        </div>
                      </div>
                    ))}
                    {!tasks.length ? (
                      <div className="text-brown-600 text-sm">Заданий пока нет</div>
                    ) : null}
                  </div>
                </Card>
              </div>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
