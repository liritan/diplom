"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Card } from "@/components/ui/common";
import { SimulationChat } from "@/components/SimulationChat";

type Test = {
  id: number;
  title: string;
  description: string;
  type: string;
};

export default function SimulationByIdPage() {
  const params = useParams() as any;
  const testId = Number(params?.id);

  const [test, setTest] = useState<Test | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get(`/tests/${testId}`);
        const t = res.data as Test;
        if (!t || String(t.type).toLowerCase() !== "simulation") {
          setError("Симуляция не найдена");
          setTest(null);
          return;
        }
        setTest(t);
      } catch (e: any) {
        console.error(e);
        setError(e?.response?.data?.detail || "Симуляция не найдена");
        setTest(null);
      } finally {
        setLoading(false);
      }
    };

    if (Number.isFinite(testId) && testId > 0) run();
  }, [testId]);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex flex-col h-full bg-beige-100">
          <div className="p-8 text-brown-600">Загрузка...</div>
        </div>
      </AppLayout>
    );
  }

  if (error || !test) {
    return (
      <AppLayout>
        <div className="flex flex-col h-full bg-beige-100">
          <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
            <h1 className="text-2xl font-bold text-brown-800">Ролевая игра</h1>
          </div>
          <div className="p-8 overflow-y-auto">
            <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
              <div className="text-brown-800 font-bold">Ошибка</div>
              <div className="text-brown-600 text-sm mt-2">{error || "Симуляция не найдена"}</div>
            </Card>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <SimulationChat
        scenario={`sim:${test.id}`}
        title={test.title}
        subtitle={test.description || "Потренируйтесь в формате чата"}
        systemIntro={test.description || "Здравствуйте! Давайте начнём симуляцию."}
        apiPaths={{
          reply: `/tests/${test.id}/simulation/reply`,
          voice: `/tests/${test.id}/simulation/voice`,
          submit: `/tests/${test.id}/simulation/submit`,
        }}
      />
    </AppLayout>
  );
}
