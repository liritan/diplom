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
  questions?: Question[];
};

type Question = {
  id: number;
  test_id: number;
  text: string;
  type: string;
  options?: any[] | null;
  correct_answer?: any | null;
};

type PlanMaterial = {
  id: string;
  title: string;
  url: string;
  type: string;
  skill: string;
  difficulty: string;
};

type PlanTask = {
  id: string;
  description: string;
  skill: string;
  status: string;
  completed_at?: string | null;
};

type PlanContent = {
  weaknesses: string[];
  materials: PlanMaterial[];
  tasks: PlanTask[];
  recommended_tests: Array<{ test_id: number; title: string; reason: string }>;
};

type DevelopmentPlan = {
  id: number;
  user_id: number;
  generated_at: string;
  is_archived: boolean;
  content: PlanContent;
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

  const [tab, setTab] = useState<"users" | "content" | "plans">("users");

  const [users, setUsers] = useState<AdminUserStats[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserProfile, setSelectedUserProfile] = useState<Profile | null>(null);
  const [selectedUserAnalysis, setSelectedUserAnalysis] = useState<AnalysisResult[]>([]);
  const [selectedUserTests, setSelectedUserTests] = useState<UserTestResult[]>([]);
  const [selectedUserCases, setSelectedUserCases] = useState<CaseSolution[]>([]);
  const [newUserPassword, setNewUserPassword] = useState("");
  const [userFullNameDraft, setUserFullNameDraft] = useState("");

  const [tests, setTests] = useState<Test[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);

  const [testEdit, setTestEdit] = useState<{ title: string; description: string; type: string }>(
    { title: "", description: "", type: "quiz" }
  );
  const [questionEdits, setQuestionEdits] = useState<Record<number, { text?: string; type?: string; options?: string }>>({});

  const [newTest, setNewTest] = useState({ title: "", description: "", type: "quiz" });
  const [newQuestion, setNewQuestion] = useState({ text: "", type: "text", options: "" });

  const [activePlan, setActivePlan] = useState<DevelopmentPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [newMaterial, setNewMaterial] = useState<PlanMaterial>({
    id: "",
    title: "",
    url: "",
    type: "article",
    skill: "",
    difficulty: "beginner",
  });
  const [newTask, setNewTask] = useState<PlanTask>({
    id: "",
    description: "",
    skill: "",
    status: "pending",
    completed_at: "",
  });
  const [materialEdits, setMaterialEdits] = useState<Record<string, Partial<PlanMaterial>>>({});
  const [taskEdits, setTaskEdits] = useState<Record<string, Partial<PlanTask>>>({});

  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!message) return;
    const timeoutId = window.setTimeout(() => setMessage(null), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [message]);

  const isAdmin = user?.role === "admin";

  const loadUsers = async () => {
    const res = await api.get<AdminUserStats[]>("/admin/users", { params: { limit: 200 } });
    setUsers(res.data);
  };

  const saveSelectedTest = async () => {
    if (!selectedTestId) return;
    setMessage(null);
    try {
      await api.patch(`/admin/tests/${selectedTestId}`, {
        title: testEdit.title,
        description: testEdit.description,
        type: testEdit.type,
      });
      setMessage("Тест обновлён");
      await loadTests();
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка обновления теста");
    }
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

  const setUserPassword = async () => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.post(`/admin/users/${selectedUserId}/password`, { new_password: newUserPassword });
      setNewUserPassword("");
      setMessage("Пароль пользователя обновлён");
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка смены пароля");
    }
  };

  const loadTests = async () => {
    const res = await api.get<Test[]>("/admin/tests", { params: { limit: 200 } });
    setTests(res.data);
  };

  const loadQuestions = async (testId: number) => {
    const res = await api.get<Question[]>(`/admin/tests/${testId}/questions`);
    setQuestions(res.data);
    setQuestionEdits({});
  };

  const loadPlan = async (userId: number) => {
    setPlanLoading(true);
    try {
      const res = await api.get<DevelopmentPlan>(`/admin/users/${userId}/plan`);
      setActivePlan(res.data);
      setMaterialEdits({});
      setTaskEdits({});
    } catch (e: any) {
      console.error(e);
      setActivePlan(null);
      setMessage(e?.response?.data?.detail || "Ошибка загрузки плана развития");
    } finally {
      setPlanLoading(false);
    }
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

  useEffect(() => {
    if (tab !== "plans" || !selectedUserId) {
      setActivePlan(null);
      return;
    }

    loadPlan(selectedUserId).catch(() => undefined);
  }, [tab, selectedUserId]);

  const selectedUser = useMemo(
    () => users.find((u) => u.user.id === selectedUserId) ?? null,
    [users, selectedUserId]
  );

  useEffect(() => {
    setUserFullNameDraft(selectedUser?.user.full_name ?? "");
  }, [selectedUser?.user.full_name, selectedUserId]);

  const saveUserFullName = async () => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.patch(`/admin/users/${selectedUserId}`, { full_name: userFullNameDraft });
      setMessage("Имя пользователя обновлено");
      await loadUsers();
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка обновления имени");
    }
  };

  const selectedTest = useMemo(
    () => tests.find((t) => t.id === selectedTestId) ?? null,
    [tests, selectedTestId]
  );

  useEffect(() => {
    if (!selectedTest) {
      setTestEdit({ title: "", description: "", type: "quiz" });
      return;
    }

    setTestEdit({
      title: selectedTest.title ?? "",
      description: selectedTest.description ?? "",
      type: selectedTest.type ?? "quiz",
    });
  }, [selectedTest]);

  const planMaterials = useMemo(() => activePlan?.content.materials ?? [], [activePlan]);
  const planTasks = useMemo(() => activePlan?.content.tasks ?? [], [activePlan]);
  const planWeaknesses = useMemo(() => activePlan?.content.weaknesses ?? [], [activePlan]);
  const planRecommendations = useMemo(
    () => activePlan?.content.recommended_tests ?? [],
    [activePlan]
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

  const updateQuestionDraft = (questionId: number, key: "text" | "type" | "options", value: string) => {
    setQuestionEdits((prev) => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        [key]: value,
      },
    }));
  };

  const saveQuestion = async (questionId: number) => {
    const draft = questionEdits[questionId];
    if (!draft || Object.keys(draft).length === 0) {
      setMessage("Нет изменений для вопроса");
      return;
    }

    setMessage(null);
    try {
      const optionsParsed = draft.options !== undefined
        ? (draft.options.trim() ? JSON.parse(draft.options) : null)
        : undefined;

      await api.patch(`/admin/questions/${questionId}`, {
        ...(draft.text !== undefined ? { text: draft.text } : {}),
        ...(draft.type !== undefined ? { type: draft.type } : {}),
        ...(draft.options !== undefined ? { options: optionsParsed } : {}),
      });

      setQuestionEdits((prev) => {
        const { [questionId]: _, ...rest } = prev;
        return rest;
      });

      setMessage("Вопрос обновлён");
      if (selectedTestId) await loadQuestions(selectedTestId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка обновления вопроса (проверь JSON options)");
    }
  };

  const updateMaterialDraft = (materialId: string, key: keyof PlanMaterial, value: string) => {
    setMaterialEdits((prev) => ({
      ...prev,
      [materialId]: {
        ...prev[materialId],
        [key]: value,
      },
    }));
  };

  const updateTaskDraft = (taskId: string, key: keyof PlanTask, value: string) => {
    setTaskEdits((prev) => ({
      ...prev,
      [taskId]: {
        ...prev[taskId],
        [key]: value,
      },
    }));
  };

  const createMaterial = async () => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.post(`/admin/users/${selectedUserId}/materials`, newMaterial);
      setNewMaterial({ id: "", title: "", url: "", type: "article", skill: "", difficulty: "beginner" });
      setMessage("Материал добавлен");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка добавления материала");
    }
  };

  const saveMaterial = async (materialId: string) => {
    if (!selectedUserId) return;
    const draft = materialEdits[materialId];
    if (!draft || Object.keys(draft).length === 0) {
      setMessage("Нет изменений для материала");
      return;
    }
    setMessage(null);
    try {
      await api.patch(`/admin/users/${selectedUserId}/materials/${materialId}`, draft);
      setMaterialEdits((prev) => {
        const { [materialId]: _, ...rest } = prev;
        return rest;
      });
      setMessage("Материал обновлён");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка обновления материала");
    }
  };

  const deleteMaterial = async (materialId: string) => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.delete(`/admin/users/${selectedUserId}/materials/${materialId}`);
      setMessage("Материал удалён");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка удаления материала");
    }
  };

  const createTask = async () => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.post(`/admin/users/${selectedUserId}/tasks`, newTask);
      setNewTask({ id: "", description: "", skill: "", status: "pending", completed_at: "" });
      setMessage("Задание добавлено");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка добавления задания");
    }
  };

  const saveTask = async (taskId: string) => {
    if (!selectedUserId) return;
    const draft = taskEdits[taskId];
    if (!draft || Object.keys(draft).length === 0) {
      setMessage("Нет изменений для задания");
      return;
    }
    setMessage(null);
    try {
      await api.patch(`/admin/users/${selectedUserId}/tasks/${taskId}`, draft);
      setTaskEdits((prev) => {
        const { [taskId]: _, ...rest } = prev;
        return rest;
      });
      setMessage("Задание обновлено");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка обновления задания");
    }
  };

  const deleteTask = async (taskId: string) => {
    if (!selectedUserId) return;
    setMessage(null);
    try {
      await api.delete(`/admin/users/${selectedUserId}/tasks/${taskId}`);
      setMessage("Задание удалено");
      await loadPlan(selectedUserId);
    } catch (e: any) {
      console.error(e);
      setMessage(e?.response?.data?.detail || "Ошибка удаления задания");
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
                <button
                  type="button"
                  onClick={() => setTab("plans")}
                  className={`px-4 py-2 rounded-lg border text-sm font-bold ${
                    tab === "plans"
                      ? "bg-white border-beige-300 text-brown-800 shadow-sm"
                      : "bg-beige-200 border-beige-300 text-brown-800 hover:bg-white"
                  }`}
                >
                  Планы развития
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
                            <div className="text-sm font-bold text-brown-800">
                              {(u.user.full_name && u.user.full_name.trim()) ? u.user.full_name : u.user.email}
                            </div>
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
                          <div className="text-brown-800 text-sm">Имя: <span className="font-bold">{selectedUser.user.full_name || "—"}</span></div>
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

                          <div className="mt-6 bg-beige-100 border border-beige-300 rounded-xl p-5">
                            <div className="text-sm font-bold text-brown-800">Изменить имя пользователя</div>
                            <div className="mt-3 flex flex-col md:flex-row gap-3">
                              <Input
                                value={userFullNameDraft}
                                onChange={(e) => setUserFullNameDraft(e.target.value)}
                                placeholder="Имя (опц.)"
                                className="bg-white border-beige-300"
                              />
                              <Button
                                onClick={saveUserFullName}
                                className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                              >
                                Сохранить
                              </Button>
                            </div>
                          </div>

                          <div className="mt-6 bg-beige-100 border border-beige-300 rounded-xl p-5">
                            <div className="text-sm font-bold text-brown-800">Сменить пароль пользователя</div>
                            <div className="mt-3 flex flex-col md:flex-row gap-3">
                              <Input
                                value={newUserPassword}
                                onChange={(e) => setNewUserPassword(e.target.value)}
                                placeholder="Новый пароль"
                                type="password"
                                className="bg-white border-beige-300"
                              />
                              <Button
                                onClick={setUserPassword}
                                disabled={!newUserPassword.trim()}
                                className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                              >
                                Сохранить
                              </Button>
                            </div>
                          </div>
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
              ) : tab === "content" ? (
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

                    {selectedTest ? (
                      <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                        <h3 className="text-lg font-bold text-brown-800">Редактировать тест</h3>
                        <div className="text-brown-600 text-sm mt-2">
                          ID: <span className="font-bold text-brown-800">{selectedTest.id}</span>
                        </div>

                        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Input
                            value={testEdit.title}
                            onChange={(e) => setTestEdit((p) => ({ ...p, title: e.target.value }))}
                            placeholder="Название"
                            className="bg-beige-100 border-beige-300"
                          />
                          <Input
                            value={testEdit.type}
                            onChange={(e) => setTestEdit((p) => ({ ...p, type: e.target.value }))}
                            placeholder="Тип (quiz|case|simulation)"
                            className="bg-beige-100 border-beige-300"
                          />
                          <div className="md:col-span-2">
                            <textarea
                              value={testEdit.description}
                              onChange={(e) => setTestEdit((p) => ({ ...p, description: e.target.value }))}
                              placeholder="Описание"
                              className="w-full min-h-[120px] bg-beige-100 border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                            />
                          </div>
                        </div>

                        <div className="mt-4">
                          <Button
                            onClick={saveSelectedTest}
                            disabled={!testEdit.title.trim() || !testEdit.type.trim()}
                            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
                          >
                            Сохранить
                          </Button>
                        </div>
                      </Card>
                    ) : null}

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Вопросы</h3>
                      {selectedTest ? (
                        <>
                          <div className="text-brown-600 text-sm mt-2">Тест: <span className="font-bold text-brown-800">{selectedTest.title}</span> (id: {selectedTest.id})</div>
                          <div className="mt-4 space-y-3">
                            {questions.map((q) => (
                              <div key={q.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  <Input
                                    value={questionEdits[q.id]?.text ?? q.text}
                                    onChange={(e) => updateQuestionDraft(q.id, "text", e.target.value)}
                                    placeholder="Текст вопроса"
                                    className="bg-white border-beige-300"
                                  />
                                  <Input
                                    value={questionEdits[q.id]?.type ?? q.type}
                                    onChange={(e) => updateQuestionDraft(q.id, "type", e.target.value)}
                                    placeholder="Тип"
                                    className="bg-white border-beige-300"
                                  />
                                  <div className="md:col-span-2">
                                    <textarea
                                      value={
                                        questionEdits[q.id]?.options
                                          ?? (q.options ? JSON.stringify(q.options) : "")
                                      }
                                      onChange={(e) => updateQuestionDraft(q.id, "options", e.target.value)}
                                      placeholder='Options JSON (пример: [{"text":"A","value":1}]) — можно оставить пустым'
                                      className="w-full min-h-[110px] bg-white border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                                    />
                                  </div>
                                </div>

                                <div className="mt-3 flex flex-wrap gap-2">
                                  <Button
                                    onClick={() => saveQuestion(q.id)}
                                    className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-4 rounded-lg uppercase text-xs tracking-wider"
                                  >
                                    Сохранить
                                  </Button>
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
              ) : (
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
                            onClick={() => {
                              setSelectedUserId(u.user.id);
                            }}
                            className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
                              active
                                ? "bg-beige-100 border-beige-300 shadow-sm"
                                : "bg-white border-beige-300 hover:bg-beige-100"
                            }`}
                          >
                            <div className="text-sm font-bold text-brown-800">{u.user.email}</div>
                            <div className="text-xs text-brown-600 mt-1">role: {u.user.role}</div>
                          </button>
                        );
                      })}
                      {!users.length ? <div className="text-brown-600 text-sm">Нет пользователей</div> : null}
                    </div>
                  </Card>

                  <div className="lg:col-span-2 space-y-8">
                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Активный план развития</h3>
                      {!selectedUser ? (
                        <div className="text-brown-600 text-sm mt-3">Выберите пользователя слева</div>
                      ) : planLoading ? (
                        <div className="text-brown-600 text-sm mt-3">Загрузка плана...</div>
                      ) : !activePlan ? (
                        <div className="text-brown-600 text-sm mt-3">Активный план не найден</div>
                      ) : (
                        <div className="mt-4 space-y-4">
                          <div className="text-brown-800 text-sm">
                            План #{activePlan.id} • создан: <span className="font-bold">{formatDate(activePlan.generated_at)}</span>
                          </div>
                          <div className="text-brown-600 text-xs">Статус: {activePlan.is_archived ? "архив" : "активный"}</div>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                            <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">Материалы: <span className="font-bold">{planMaterials.length}</span></div>
                            <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">Задания: <span className="font-bold">{planTasks.length}</span></div>
                            <div className="bg-beige-100 border border-beige-300 rounded-lg px-4 py-3 text-brown-800">Рекомендации: <span className="font-bold">{planRecommendations.length}</span></div>
                          </div>
                          <div>
                            <div className="text-sm font-bold text-brown-800">Зоны роста</div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {planWeaknesses.length ? (
                                planWeaknesses.map((w) => (
                                  <span key={w} className="bg-beige-100 border border-beige-300 rounded-full px-3 py-1 text-xs text-brown-800">
                                    {w}
                                  </span>
                                ))
                              ) : (
                                <span className="text-brown-600 text-sm">Нет данных</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </Card>

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <div className="flex items-center justify-between gap-4">
                        <h3 className="text-lg font-bold text-brown-800">Материалы</h3>
                        {selectedUserId ? (
                          <Button
                            onClick={createMaterial}
                            disabled={!newMaterial.id.trim() || !newMaterial.title.trim() || !newMaterial.url.trim()}
                            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                          >
                            Добавить
                          </Button>
                        ) : null}
                      </div>

                      {selectedUserId ? (
                        <div className="mt-4 space-y-6">
                          <div className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                            <div className="text-sm font-bold text-brown-800">Новый материал</div>
                            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                              <Input
                                value={newMaterial.id}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, id: e.target.value }))}
                                placeholder="ID"
                                className="bg-white border-beige-300"
                              />
                              <Input
                                value={newMaterial.title}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, title: e.target.value }))}
                                placeholder="Название"
                                className="bg-white border-beige-300"
                              />
                              <Input
                                value={newMaterial.url}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, url: e.target.value }))}
                                placeholder="URL"
                                className="bg-white border-beige-300"
                              />
                              <Input
                                value={newMaterial.skill}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, skill: e.target.value }))}
                                placeholder="Навык"
                                className="bg-white border-beige-300"
                              />
                              <select
                                value={newMaterial.type}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, type: e.target.value }))}
                                className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                              >
                                <option value="article">article</option>
                                <option value="video">video</option>
                                <option value="course">course</option>
                              </select>
                              <select
                                value={newMaterial.difficulty}
                                onChange={(e) => setNewMaterial((p) => ({ ...p, difficulty: e.target.value }))}
                                className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                              >
                                <option value="beginner">beginner</option>
                                <option value="intermediate">intermediate</option>
                                <option value="advanced">advanced</option>
                              </select>
                            </div>
                          </div>

                          <div className="space-y-3">
                            {planMaterials.map((m) => {
                              const draft = materialEdits[m.id] ?? {};
                              return (
                                <div key={m.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5 space-y-4">
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <Input value={m.id} disabled className="bg-beige-200 border-beige-300" />
                                    <Input
                                      value={draft.title ?? m.title}
                                      onChange={(e) => updateMaterialDraft(m.id, "title", e.target.value)}
                                      placeholder="Название"
                                      className="bg-white border-beige-300"
                                    />
                                    <Input
                                      value={draft.url ?? m.url}
                                      onChange={(e) => updateMaterialDraft(m.id, "url", e.target.value)}
                                      placeholder="URL"
                                      className="bg-white border-beige-300"
                                    />
                                    <Input
                                      value={draft.skill ?? m.skill}
                                      onChange={(e) => updateMaterialDraft(m.id, "skill", e.target.value)}
                                      placeholder="Навык"
                                      className="bg-white border-beige-300"
                                    />
                                    <select
                                      value={draft.type ?? m.type}
                                      onChange={(e) => updateMaterialDraft(m.id, "type", e.target.value)}
                                      className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                                    >
                                      <option value="article">article</option>
                                      <option value="video">video</option>
                                      <option value="course">course</option>
                                    </select>
                                    <select
                                      value={draft.difficulty ?? m.difficulty}
                                      onChange={(e) => updateMaterialDraft(m.id, "difficulty", e.target.value)}
                                      className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                                    >
                                      <option value="beginner">beginner</option>
                                      <option value="intermediate">intermediate</option>
                                      <option value="advanced">advanced</option>
                                    </select>
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    <Button
                                      onClick={() => saveMaterial(m.id)}
                                      className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                                    >
                                      Сохранить
                                    </Button>
                                    <Button
                                      onClick={() => deleteMaterial(m.id)}
                                      className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                                    >
                                      Удалить
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                            {!planMaterials.length ? (
                              <div className="text-brown-600 text-sm">Материалов нет</div>
                            ) : null}
                          </div>
                        </div>
                      ) : (
                        <div className="text-brown-600 text-sm mt-3">Выберите пользователя, чтобы управлять материалами</div>
                      )}
                    </Card>

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <div className="flex items-center justify-between gap-4">
                        <h3 className="text-lg font-bold text-brown-800">Задания</h3>
                        {selectedUserId ? (
                          <Button
                            onClick={createTask}
                            disabled={!newTask.id.trim() || !newTask.description.trim()}
                            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                          >
                            Добавить
                          </Button>
                        ) : null}
                      </div>

                      {selectedUserId ? (
                        <div className="mt-4 space-y-6">
                          <div className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                            <div className="text-sm font-bold text-brown-800">Новое задание</div>
                            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                              <Input
                                value={newTask.id}
                                onChange={(e) => setNewTask((p) => ({ ...p, id: e.target.value }))}
                                placeholder="ID"
                                className="bg-white border-beige-300"
                              />
                              <Input
                                value={newTask.skill}
                                onChange={(e) => setNewTask((p) => ({ ...p, skill: e.target.value }))}
                                placeholder="Навык"
                                className="bg-white border-beige-300"
                              />
                              <div className="md:col-span-2">
                                <textarea
                                  value={newTask.description}
                                  onChange={(e) => setNewTask((p) => ({ ...p, description: e.target.value }))}
                                  placeholder="Описание задания"
                                  className="w-full min-h-[110px] bg-white border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                                />
                              </div>
                              <select
                                value={newTask.status}
                                onChange={(e) => setNewTask((p) => ({ ...p, status: e.target.value }))}
                                className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                              >
                                <option value="pending">pending</option>
                                <option value="completed">completed</option>
                              </select>
                              <Input
                                value={newTask.completed_at ?? ""}
                                onChange={(e) => setNewTask((p) => ({ ...p, completed_at: e.target.value }))}
                                placeholder="completed_at (опц.)"
                                className="bg-white border-beige-300"
                              />
                            </div>
                          </div>

                          <div className="space-y-3">
                            {planTasks.map((t) => {
                              const draft = taskEdits[t.id] ?? {};
                              return (
                                <div key={t.id} className="bg-beige-100 border border-beige-300 rounded-xl p-5 space-y-4">
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <Input value={t.id} disabled className="bg-beige-200 border-beige-300" />
                                    <Input
                                      value={draft.skill ?? t.skill}
                                      onChange={(e) => updateTaskDraft(t.id, "skill", e.target.value)}
                                      placeholder="Навык"
                                      className="bg-white border-beige-300"
                                    />
                                    <div className="md:col-span-2">
                                      <textarea
                                        value={draft.description ?? t.description}
                                        onChange={(e) => updateTaskDraft(t.id, "description", e.target.value)}
                                        placeholder="Описание"
                                        className="w-full min-h-[110px] bg-white border border-beige-300 rounded-xl p-4 text-brown-800 outline-none"
                                      />
                                    </div>
                                    <select
                                      value={draft.status ?? t.status}
                                      onChange={(e) => updateTaskDraft(t.id, "status", e.target.value)}
                                      className="h-10 rounded-md border border-beige-300 bg-white px-3 text-sm text-brown-800"
                                    >
                                      <option value="pending">pending</option>
                                      <option value="completed">completed</option>
                                    </select>
                                    <Input
                                      value={draft.completed_at ?? t.completed_at ?? ""}
                                      onChange={(e) => updateTaskDraft(t.id, "completed_at", e.target.value)}
                                      placeholder="completed_at (опц.)"
                                      className="bg-white border-beige-300"
                                    />
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    <Button
                                      onClick={() => saveTask(t.id)}
                                      className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                                    >
                                      Сохранить
                                    </Button>
                                    <Button
                                      onClick={() => deleteTask(t.id)}
                                      className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-5 rounded-lg uppercase text-xs tracking-wider"
                                    >
                                      Удалить
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                            {!planTasks.length ? (
                              <div className="text-brown-600 text-sm">Заданий нет</div>
                            ) : null}
                          </div>
                        </div>
                      ) : (
                        <div className="text-brown-600 text-sm mt-3">Выберите пользователя, чтобы управлять заданиями</div>
                      )}
                    </Card>

                    <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
                      <h3 className="text-lg font-bold text-brown-800">Рекомендации</h3>
                      {!selectedUserId ? (
                        <div className="text-brown-600 text-sm mt-3">Выберите пользователя, чтобы видеть рекомендации</div>
                      ) : !planRecommendations.length ? (
                        <div className="text-brown-600 text-sm mt-3">Рекомендаций нет</div>
                      ) : (
                        <div className="mt-4 space-y-3">
                          {planRecommendations.map((rec) => (
                            <div key={rec.test_id} className="bg-beige-100 border border-beige-300 rounded-xl p-5">
                              <div className="text-sm font-bold text-brown-800">{rec.title}</div>
                              <div className="text-xs text-brown-600 mt-2">{rec.reason}</div>
                            </div>
                          ))}
                        </div>
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
