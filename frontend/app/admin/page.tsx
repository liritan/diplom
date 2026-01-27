"use client";

import { useEffect, useMemo, useState } from "react";
import AppLayout from "@/components/AppLayout";
import api from "@/lib/api";
import { Button, Card, Input } from "@/components/ui/common";
import { useAuth } from "@/context/AuthContext";

type AdminUserStats = {
  user: { id: number; email: string; full_name?: string; role: string; is_active?: boolean };
  analysis_count: number;
  test_results_count: number;
  case_solutions_count: number;
};

type Profile = {
  id: number;
  user_id: number;
  communication_score: number;
  emotional_intelligence_score: number;
  critical_thinking_score: number;
  time_management_score: number;
  leadership_score: number;
  updated_at: string;
};

type AnalysisResult = {
  id: number;
  task_id: string;
  user_id: number;
  created_at: string;
  communication_score: number;
  emotional_intelligence_score: number;
  critical_thinking_score: number;
  time_management_score: number;
  leadership_score: number;
  feedback?: string | null;
};

type UserTestResult = {
  id: number;
  user_id: number;
  test_id: number;
  score?: number | null;
  ai_analysis?: string | null;
  completed_at: string;
};

type CaseSolution = {
  id: number;
  user_id: number;
  test_id: number;
  solution: string;
  analysis_task_id?: string | null;
  created_at: string;
};

type Test = {
  id: number;
  title: string;
  description: string;
  type: string;
  created_at: string;
};

type Question = {
  id: number;
  test_id: number;
  text: string;
  type: string;
  options?: any[] | null;
  correct_answer?: any | null;
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

export default function AdminPage() {
  const { user } = useAuth();

  const [tab, setTab] = useState<"users" | "content">("users");

  const [users, setUsers] = useState<AdminUserStats[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserProfile, setSelectedUserProfile] = useState<Profile | null>(null);
  const [selectedUserAnalysis, setSelectedUserAnalysis] = useState<AnalysisResult[]>([]);
  const [selectedUserTests, setSelectedUserTests] = useState<UserTestResult[]>([]);
  const [selectedUserCases, setSelectedUserCases] = useState<CaseSolution[]>([]);

  const [tests, setTests] = useState<Test[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);

  const [newTest, setNewTest] = useState({ title: "", description: "", type: "quiz" });
  const [newQuestion, setNewQuestion] = useState({ text: "", type: "text", options: "" });

  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  const isAdmin = user?.role === "admin";

  const loadUsers = async () => {
    const res = await api.get<AdminUserStats[]>("/admin/users", { params: { limit: 200 } });
    setUsers(res.data);
  };

  const loadUserDetails = async (userId: number) => {
    const [p, a, t, c] = await Promise.all([
      api.get<Profile | null>(`/admin/users/${userId}/profile`),
      api.get<AnalysisResult[]>(`/admin/users/${userId}/analysis`, { params: { limit: 50 } }),
      api.get<UserTestResult[]>(`/admin/users/${userId}/tests`, { params: { limit: 100 } }),
      api.get<CaseSolution[]>(`/admin/users/${userId}/cases`, { params: { limit: 100 } }),
    ]);

    setSelectedUserProfile(p.data);
    setSelectedUserAnalysis(a.data);
    setSelectedUserTests(t.data);
    setSelectedUserCases(c.data);
  };

  const loadTests = async () => {
    const res = await api.get<Test[]>("/admin/tests", { params: { limit: 200 } });
    setTests(res.data);
  };

  const loadQuestions = async (testId: number) => {
    const res = await api.get<Question[]>(`/admin/tests/${testId}/questions`);
    setQuestions(res.data);
  };

  useEffect(() => {
    const run = async () => {
      if (!isAdmin) {
        setLoading(false);
        return;
      }

      try {
        await Promise.all([loadUsers(), loadTests()]);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [isAdmin]);

  const selectedUser = useMemo(
    () => users.find((u) => u.user.id === selectedUserId) ?? null,
    [users, selectedUserId]
  );

  const selectedTest = useMemo(
    () => tests.find((t) => t.id === selectedTestId) ?? null,
    [tests, selectedTestId]
  );

  const createTest = async () => {
    setMessage(null);
    try {
      await api.post("/admin/tests", newTest);
      setNewTest({ title: "", description: "", type: "quiz" });
      setMessage("Тест создан");
      await loadTests();
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка создания теста");
    }
  };

  const deleteTest = async (testId: number) => {
    setMessage(null);
    try {
      await api.delete(`/admin/tests/${testId}`);
      setMessage("Тест удалён");
      if (selectedTestId === testId) {
        setSelectedTestId(null);
        setQuestions([]);
      }
      await loadTests();
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка удаления теста");
    }
  };

  const createQuestion = async () => {
    if (!selectedTestId) return;
    setMessage(null);
    try {
      const optionsParsed = newQuestion.options.trim()
        ? JSON.parse(newQuestion.options)
        : null;

      await api.post(`/admin/tests/${selectedTestId}/questions`, {
        text: newQuestion.text,
        type: newQuestion.type,
        options: optionsParsed,
        correct_answer: null,
      });
      setNewQuestion({ text: "", type: "text", options: "" });
      setMessage("Вопрос добавлен");
      await loadQuestions(selectedTestId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка добавления вопроса (проверь JSON options)");
    }
  };

  const deleteQuestion = async (questionId: number) => {
    setMessage(null);
    try {
      await api.delete(`/admin/questions/${questionId}`);
      setMessage("Вопрос удалён");
      if (selectedTestId) await loadQuestions(selectedTestId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка удаления вопроса");
    }
  };

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-beige-100">
        <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
          <h1 className="text-2xl font-bold text-brown-800">Админ-панель</h1>
          <p className="text-brown-600 text-sm mt-1">Пользователи, прогресс и управление контентом</p>
        </div>

        <div className="p-8 overflow-y-auto space-y-6">
          {!isAdmin ? (
            <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
              <div className="text-brown-800 font-bold">Доступ запрещён</div>
              <div className="text-brown-600 text-sm mt-2">Эта страница доступна только администраторам.</div>
            </Card>
          ) : loading ? (
            <div className="text-brown-600">Загрузка...</div>
          ) : (
            <>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => setTab("users")}
                  className={`px-4 py-2 rounded-lg border text-sm font-bold ${
                    tab === "users"
                      ? "bg-white border-beige-300 text-brown-800 shadow-sm"
                      : "bg-beige-200 border-beige-300 text-brown-800 hover:bg-white"
                  }`}
                >
                  Пользователи
                </button>
                <button
                  type="button"
                  onClick={() => setTab("content")}
                  className={`px-4 py-2 rounded-lg border text-sm font-bold ${
                    tab === "content"
                      ? "bg-white border-beige-300 text-brown-800 shadow-sm"
                      : "bg-beige-200 border-beige-300 text-brown-800 hover:bg-white"
                  }`}
                >
                  Тесты и вопросы
                </button>
              </div>

              {message ? (
                <div className="bg-beige-200 border border-beige-300 rounded-xl px-6 py-4 text-brown-800">{message}</div>
              ) : null}

              {tab === "users" ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 lg:col-span-1">
                    <h3 className="text-lg font-bold text-brown-800">Пользователи</h3>
                    <div className="mt-4 space-y-2">
                      {users.map((u) => {
                        const active = selectedUserId === u.user.id;
                        return (
                          <button
                            key={u.user.id}
                            type="button"
                            onClick={async () => {
                              setSelectedUserId(u.user.id);
                              await loadUserDetails(u.user.id);
                            }}
                            className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
                              active
                                ? "bg-beige-100 border-beige-300 shadow-sm"
                                : "bg-white border-beige-300 hover:bg-beige-100"
                            }`}
                          >
                            <div className="text-sm font-bold text-brown-800">{u.user.email}</div>
                            <div className="text-xs text-brown-600 mt-1">
                              role: {u.user.role} • analyses: {u.analysis_count} • tests: {u.test_results_count} • cases: {u.case_solutions_count}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </Card>

                  <div className="lg:col-span-2 space-y-8">
                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Профиль пользователя</h3>
                      {selectedUser ? (
                        <div className="mt-4 space-y-3">
                          <div className="text-brown-800 text-sm">ID: <span className="font-bold">{selectedUser.user.id}</span></div>
                          <div className="text-brown-800 text-sm">Email: <span className="font-bold">{selectedUser.user.email}</span></div>
                          <div className="text-brown-800 text-sm">Role: <span className="font-bold">{selectedUser.user.role}</span></div>

                          {selectedUserProfile ? (
                            <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                              <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">Comm: <span className="font-bold">{Math.round(selectedUserProfile.communication_score)}</span></div>
                              <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">EI: <span className="font-bold">{Math.round(selectedUserProfile.emotional_intelligence_score)}</span></div>
                              <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">CT: <span className="font-bold">{Math.round(selectedUserProfile.critical_thinking_score)}</span></div>
                              <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">TM: <span className="font-bold">{Math.round(selectedUserProfile.time_management_score)}</span></div>
                              <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">Lead: <span className="font-bold">{Math.round(selectedUserProfile.leadership_score)}</span></div>
                            </div>
                          ) : (
                            <div className="text-brown-600 text-sm mt-3">Профиль не создан</div>
                          )}
                        </div>
                      ) : (
                        <div className="text-brown-600 text-sm mt-3">Выберите пользователя слева</div>
                      )}
                    </Card>

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Последние анализы</h3>
                      <div className="mt-4 space-y-3">
                        {selectedUserAnalysis.length ? (
                          selectedUserAnalysis.map((a) => (
                            <div key={a.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                              <div className="text-xs text-brown-600">{formatDate(a.created_at)} • task {a.task_id}</div>
                              {a.feedback ? (
                                <div className="mt-2 text-sm text-brown-800 whitespace-pre-wrap">{a.feedback}</div>
                              ) : null}
                            </div>
                          ))
                        ) : (
                          <div className="text-brown-600 text-sm">Нет анализов</div>
                        )}
                      </div>
                    </Card>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                      <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                        <h3 className="text-lg font-bold text-brown-800">Тесты</h3>
                        <div className="mt-4 space-y-3">
                          {selectedUserTests.length ? (
                            selectedUserTests.map((t) => (
                              <div key={t.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                                <div className="text-xs text-brown-600">{formatDate(t.completed_at)} • test_id {t.test_id}</div>
                                {t.ai_analysis ? (
                                  <div className="mt-2 text-sm text-brown-800 whitespace-pre-wrap">{t.ai_analysis}</div>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <div className="text-brown-600 text-sm">Нет тестов</div>
                          )}
                        </div>
                      </Card>

                      <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                        <h3 className="text-lg font-bold text-brown-800">Кейсы/симуляции</h3>
                        <div className="mt-4 space-y-3">
                          {selectedUserCases.length ? (
                            selectedUserCases.map((c) => (
                              <div key={c.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                                <div className="text-xs text-brown-600">{formatDate(c.created_at)} • test_id {c.test_id}</div>
                                <div className="mt-2 text-sm text-brown-800 whitespace-pre-wrap">{c.solution}</div>
                              </div>
                            ))
                          ) : (
                            <div className="text-brown-600 text-sm">Нет кейсов</div>
                          )}
                        </div>
                      </Card>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6 lg:col-span-1">
                    <h3 className="text-lg font-bold text-brown-800">Тесты</h3>
                    <div className="mt-4 space-y-2">
                      {tests.map((t) => {
                        const active = selectedTestId === t.id;
                        return (
                          <div key={t.id} className={`border rounded-xl p-4 ${active ? "bg-beige-100 border-beige-300" : "bg-white border-beige-300"}`}>
                            <button
                              type="button"
                              onClick={async () => {
                                setSelectedTestId(t.id);
                                await loadQuestions(t.id);
                              }}
                              className="w-full text-left"
                            >
                              <div className="text-sm font-bold text-brown-800">{t.title}</div>
                              <div className="text-xs text-brown-600 mt-1">type: {t.type}</div>
                            </button>
                            <div className="mt-3 flex gap-2">
                              <Button
                                onClick={() => deleteTest(t.id)}
                                className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider"
                              >
                                Удалить
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                      {!tests.length ? <div className="text-brown-600 text-sm">Нет тестов</div> : null}
                    </div>
                  </Card>

                  <div className="lg:col-span-2 space-y-8">
                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Создать тест</h3>
                      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Input
                          value={newTest.title}
                          onChange={(e) => setNewTest((p) => ({ ...p, title: e.target.value }))}
                          placeholder="Название"
                          className="bg-beige-100 border-beige-300"
                        />
                        <Input
                          value={newTest.type}
                          onChange={(e) => setNewTest((p) => ({ ...p, type: e.target.value }))}
                          placeholder="Тип (quiz|case|simulation)"
                          className="bg-beige-100 border-beige-300"
                        />
                        <div className="md:col-span-2">
                          <textarea
                            value={newTest.description}
                            onChange={(e) => setNewTest((p) => ({ ...p, description: e.target.value }))}
                            placeholder="Описание"
                            className="w-full min-h-[120px] bg-beige-100 border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                          />
                        </div>
                      </div>
                      <div className="mt-4">
                        <Button
                          onClick={createTest}
                          className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                        >
                          Создать
                        </Button>
                      </div>
                    </Card>

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Вопросы</h3>
                      {selectedTest ? (
                        <>
                          <div className="text-brown-600 text-sm mt-2">Тест: <span className="font-bold text-brown-800">{selectedTest.title}</span> (id: {selectedTest.id})</div>
                          <div className="mt-4 space-y-3">
                            {questions.map((q) => (
                              <div key={q.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                                <div className="text-brown-800 font-bold">{q.text}</div>
                                <div className="text-brown-600 text-xs mt-1">type: {q.type}</div>
                                <div className="mt-3">
                                  <Button
                                    onClick={() => deleteQuestion(q.id)}
                                    className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider"
                                  >
                                    Удалить
                                  </Button>
                                </div>
                              </div>
                            ))}
                            {!questions.length ? (
                              <div className="text-brown-600 text-sm">Вопросов нет</div>
                            ) : null}
                          </div>

                          <div className="mt-6 bg-beige-100 border border-beige-300 rounded-xl p-5">
                            <div className="text-sm font-bold text-brown-800">Добавить вопрос</div>
                            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                              <Input
                                value={newQuestion.text}
                                onChange={(e) => setNewQuestion((p) => ({ ...p, text: e.target.value }))}
                                placeholder="Текст вопроса"
                                className="bg-white border-beige-300"
                              />
                              <Input
                                value={newQuestion.type}
                                onChange={(e) => setNewQuestion((p) => ({ ...p, type: e.target.value }))}
                                placeholder="Тип (text|multiple_choice|scale...)"
                                className="bg-white border-beige-300"
                              />
                              <div className="md:col-span-2">
                                <textarea
                                  value={newQuestion.options}
                                  onChange={(e) => setNewQuestion((p) => ({ ...p, options: e.target.value }))}
                                  placeholder='Options JSON (пример: [{"text":"A","value":1},{"text":"B","value":2}]) — можно оставить пустым'
                                  className="w-full min-h-[120px] bg-white border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                                />
                              </div>
                            </div>
                            <div className="mt-4">
                              <Button
                                onClick={createQuestion}
                                className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                              >
                                Добавить
                              </Button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="text-brown-600 text-sm mt-3">Выберите тест слева</div>
                      )}
                    </Card>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
