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

function typeLabel(t: string) {
  if (t === "case") return "Кейс";
  if (t === "simulation") return "Симуляция";
  return "Тест";
}

function isFinalItem(test: Test) {
  const title = String(test.title || "").toLowerCase();
  const description = String(test.description || "").toLowerCase();
  return title.includes("[final]") || description.includes("[final]");
}

export default function TestsPage() {
  const [tests, setTests] = useState<Test[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await api.get("/tests");
        setTests(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const list = useMemo(
    () => tests.filter((t) => t.type !== "simulation" && !isFinalItem(t)),
    [tests]
  );

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Тесты</h1>
          <p className="text-brown-600 text-sm mt-1">Проходите тесты и кейсы — результаты попадут в аналитику и ваш профиль</p>
        </div>

        <div className="p-8 overflow-y-auto">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {list.map((t) => (
                <Card key={t.id} className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="inline-flex items-center px-3 py-1 rounded-full bg-beige-200 border border-beige-300 text-xs font-bold text-brown-800">
                        {typeLabel(t.type)}
                      </div>
                      <h3 className="text-lg font-bold text-brown-800 mt-3">{t.title}</h3>
                      <p className="text-brown-600 text-sm mt-2">{t.description}</p>
                    </div>
                    <Link href={`/tests/${t.id}`}>
                      <Button className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider">
                        Открыть
                      </Button>
                    </Link>
                  </div>
                </Card>
              ))}

              {!list.length ? (
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="text-brown-800 font-bold">Пока нет тестов</div>
                  <div className="text-brown-600 text-sm mt-2">Добавьте тесты через админку или загрузите seed.</div>
                </Card>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
