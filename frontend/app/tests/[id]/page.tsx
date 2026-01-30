"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Button, Card, Input } from "@/components/ui/common";

type Question = {
  id: number;
  test_id: number;
  text: string;
  type: string;
  options?: Array<Record<string, any>> | null;
};

type Test = {
  id: number;
  title: string;
  description: string;
  type: string;
  created_at: string;
  questions: Question[];
};

type AnalysisStatus = {
  task_id: string;
  status: string;
  result?: {
    id: number;
    task_id: string;
    created_at: string;
    communication_score: number;
    emotional_intelligence_score: number;
    critical_thinking_score: number;
    time_management_score: number;
    leadership_score: number;
    strengths?: string[] | null;
    weaknesses?: string[] | null;
    feedback?: string | null;
  } | null;
};

function isCaseType(testType: string) {
  return testType === "case";
}

function normalizeOptionLabel(opt: any) {
  if (typeof opt === "string") return opt;
  if (opt?.text) return String(opt.text);
  if (opt?.label) return String(opt.label);
  if (opt?.value !== undefined) return String(opt.value);
  return JSON.stringify(opt);
}

function statusLabel(value: string) {
  const v = String(value || "").toLowerCase();
  if (v === "pending") return "в очереди";
  if (v === "processing") return "в обработке";
  if (v === "completed") return "готово";
  if (v === "failed") return "ошибка";
  return value;
}

export default function TestDetailsPage() {
  const params = useParams() as any;
  const testId = Number(params?.id);

  const [test, setTest] = useState<Test | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [caseSolution, setCaseSolution] = useState("");

  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await api.get(`/tests/${testId}`);
        setTest(res.data);
      } catch (e: any) {
        console.error(e);
        setError(e?.response?.data?.detail || "Не удалось загрузить тест");
      } finally {
        setLoading(false);
      }
    };

    if (Number.isFinite(testId) && testId > 0) run();
  }, [testId]);

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/analysis/status/${taskId}`);
        if (cancelled) return;
        setStatus(res.data);
        if (res.data.status === "completed" || res.data.status === "failed") {
          clearInterval(interval);
        }
      } catch (e) {
        console.error(e);
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [taskId]);

  const questions = useMemo(() => test?.questions ?? [], [test]);

  const submitQuiz = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post(`/tests/${testId}/submit`, {
        answers,
      });
      setTaskId(res.data.task_id);
    } catch (e: any) {
      console.error(e);
      setError(e?.response?.data?.detail || "Ошибка отправки теста");
    } finally {
      setSubmitting(false);
    }
  };

  const submitCase = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post(`/tests/${testId}/case/submit`, {
        solution: caseSolution,
      });
      setTaskId(res.data.task_id);
    } catch (e: any) {
      console.error(e);
      setError(e?.response?.data?.detail || "Ошибка отправки решения кейса");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Тест</h1>
          <p className="text-brown-600 text-sm mt-1">Пройдите тест или решите кейс, чтобы обновить профиль и аналитику</p>
        </div>

        <div className="p-8 overflow-y-auto space-y-8">
          {loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : error ? (
            <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
              <div className="text-brown-800 font-bold">Ошибка</div>
              <div className="text-brown-600 text-sm mt-2">{error}</div>
            </Card>
          ) : test ? (
            <>
              <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                <div className="text-lg font-bold text-brown-800">{test.title}</div>
                <div className="text-brown-600 text-sm mt-2">{test.description}</div>
              </Card>

              {isCaseType(test.type) ? (
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="text-lg font-bold text-brown-800">Решение кейса</div>
                  <div className="text-brown-600 text-sm mt-2">Опишите, как бы вы действовали в этой ситуации. Чем подробнее — тем точнее анализ.</div>
                  <textarea
                    value={caseSolution}
                    onChange={(e) => setCaseSolution(e.target.value)}
                    placeholder="Напишите ваше решение..."
                    className="mt-4 w-full min-h-[180px] bg-beige-100 border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                  />
                  <div className="mt-4">
                    <Button
                      disabled={submitting || !caseSolution.trim()}
                      onClick={submitCase}
                      className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                    >
                      Отправить на анализ
                    </Button>
                  </div>
                </Card>
              ) : (
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="text-lg font-bold text-brown-800">Вопросы</div>
                  <div className="mt-4 space-y-5">
                    {questions.map((q, idx) => (
                      <div key={q.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                        <div className="text-brown-800 font-bold">{idx + 1}. {q.text}</div>
                        {q.options && q.options.length ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {q.options.map((opt, i) => {
                              const label = normalizeOptionLabel(opt);
                              const selected = String(answers[String(q.id)] ?? "") === label;
                              return (
                                <button
                                  key={i}
                                  type="button"
                                  onClick={() => setAnswers((prev) => ({ ...prev, [String(q.id)]: label }))}
                                  className={`px-4 py-2 rounded-lg border text-sm transition-colors ${
                                    selected
                                      ? "bg-white border-beige-300 text-brown-800 shadow-sm"
                                      : "bg-beige-200 border-beige-300 text-brown-800 hover:bg-white"
                                  }`}
                                >
                                  {label}
                                </button>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="mt-3">
                            <Input
                              value={String(answers[String(q.id)] ?? "")}
                              onChange={(e) => setAnswers((prev) => ({ ...prev, [String(q.id)]: e.target.value }))}
                              placeholder="Ваш ответ..."
                              className="bg-beige-100 border-beige-300"
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="mt-6">
                    <Button
                      disabled={submitting}
                      onClick={submitQuiz}
                      className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                    >
                      Отправить на анализ
                    </Button>
                  </div>
                </Card>
              )}

              {taskId ? (
                <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                  <div className="text-lg font-bold text-brown-800">Статус анализа</div>
                  <div className="text-brown-600 text-sm mt-2">Task: {taskId}</div>
                  <div className="mt-4">
                    <div className="inline-flex items-center px-3 py-1 rounded-full bg-beige-200 border border-beige-300 text-xs font-bold text-brown-800">
                      {statusLabel(status?.status || "pending")}
                    </div>
                  </div>

                  {status?.status === "completed" && status.result ? (
                    <div className="mt-5 space-y-4">
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                        <div className="text-brown-800">Коммуникация: <span className="font-bold">{Math.round(status.result.communication_score)}</span></div>
                        <div className="text-brown-800">Эмоциональный интеллект: <span className="font-bold">{Math.round(status.result.emotional_intelligence_score)}</span></div>
                        <div className="text-brown-800">Критическое мышление: <span className="font-bold">{Math.round(status.result.critical_thinking_score)}</span></div>
                        <div className="text-brown-800">Тайм-менеджмент: <span className="font-bold">{Math.round(status.result.time_management_score)}</span></div>
                        <div className="text-brown-800">Лидерство: <span className="font-bold">{Math.round(status.result.leadership_score)}</span></div>
                      </div>
                      {status.result.feedback ? (
                        <div className="text-sm text-brown-800 whitespace-pre-wrap">{status.result.feedback}</div>
                      ) : null}
                    </div>
                  ) : null}

                  {status?.status === "failed" ? (
                    <div className="mt-4 text-sm text-brown-800">Анализ не удался. Попробуйте повторить позже.</div>
                  ) : null}
                </Card>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </AppLayout>
  );
}
