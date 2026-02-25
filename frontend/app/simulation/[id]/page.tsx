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

const FINAL_SIMULATION_SUBTITLE =
  "Финальная ролевая игра блока: комплексная проверка soft skills.";

const FINAL_SIMULATION_INTRO =
  "Ситуация: вы руководите мини-проектом, и за два дня до дедлайна появляется сразу несколько проблем. " +
  "Один сотрудник срывает срок и защищается в резкой форме, второй перегружен и молчит о рисках, " +
  "а заказчик требует подтвердить финальную дату без переноса. " +
  "Ваша задача в диалоге: спокойно выстроить коммуникацию, показать эмоциональную устойчивость и эмпатию, " +
  "структурно проанализировать риски, расставить приоритеты по времени и предложить лидерский план действий. " +
  "Нужно договориться о конкретных шагах, сроках и ответственности каждого участника.";

function sanitizeFinalLabel(value: string) {
  const cleaned = String(value || "").replace(/\[FINAL\]/gi, "").trim();
  return cleaned.replace(/\s{2,}/g, " ");
}

function isFinalSimulation(test: Test) {
  const title = String(test.title || "").toLowerCase();
  const description = String(test.description || "").toLowerCase();
  return (
    title.includes("[final]") ||
    title.includes("итоговая ролевая игра") ||
    title.includes("финальн") ||
    description.includes("[final]") ||
    description.includes("итоговая ролевая игра") ||
    description.includes("финальн")
  );
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

export default function SimulationByIdPage() {
  const params = useParams() as { id?: string };
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
      } catch (e: unknown) {
        console.error(e);
        setError(apiErrorMessage(e, "Симуляция не найдена"));
        setTest(null);
      } finally {
        setLoading(false);
      }
    };

    if (Number.isFinite(testId) && testId > 0) {
      run();
    }
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

  const title = sanitizeFinalLabel(test.title);
  const isFinal = isFinalSimulation(test);
  const subtitle = isFinal
    ? FINAL_SIMULATION_SUBTITLE
    : sanitizeFinalLabel(test.description) || "Потренируйтесь в формате чата";
  const systemIntro = isFinal
    ? FINAL_SIMULATION_INTRO
    : sanitizeFinalLabel(test.description) || "Здравствуйте! Давайте начнем симуляцию.";

  return (
    <AppLayout>
      <SimulationChat
        scenario={`sim:${test.id}`}
        title={title}
        subtitle={subtitle}
        systemIntro={systemIntro}
        apiPaths={{
          reply: `/tests/${test.id}/simulation/reply`,
          voice: `/tests/${test.id}/simulation/voice`,
          submit: `/tests/${test.id}/simulation/submit`,
        }}
      />
    </AppLayout>
  );
}
