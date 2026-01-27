"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import api from "@/lib/api";
import { Button, Card } from "@/components/ui/common";

type Message = {
  id: number;
  role: "user" | "ai";
  text: string;
};

type AnalysisStatus = {
  task_id: string;
  status: string;
  result?: {
    id: number;
    task_id: string;
    created_at: string;
    feedback?: string | null;
    communication_score: number;
    emotional_intelligence_score: number;
    critical_thinking_score: number;
    time_management_score: number;
    leadership_score: number;
  } | null;
};

function buildTranscript(messages: Message[]) {
  return messages
    .map((m) => (m.role === "user" ? `Я: ${m.text}` : `Собеседник: ${m.text}`))
    .join("\n");
}

export function SimulationChat(props: {
  scenario: "interview" | "conflict" | "negotiation";
  title: string;
  subtitle: string;
  systemIntro: string;
}) {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, role: "ai", text: props.systemIntro },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

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

  const canFinish = useMemo(() => {
    const userMessages = messages.filter((m) => m.role === "user");
    return userMessages.length > 0;
  }, [messages]);

  const sendUserMessage = async () => {
    const textToSend = input.trim();
    if (!textToSend) return;

    setError(null);
    setInput("");

    const nextMessages = [...messages, { id: Date.now(), role: "user" as const, text: textToSend }];
    setMessages(nextMessages);

    setSending(true);
    try {
      const res = await api.post(`/tests/simulations/${props.scenario}/reply`, {
        messages: nextMessages.map((m) => ({ role: m.role, text: m.text })),
      });

      const reply = String(res.data?.reply ?? "").trim();
      if (reply) {
        setMessages((prev) => [...prev, { id: Date.now() + 1, role: "ai", text: reply }]);
      }
    } catch (e: any) {
      console.error(e);
      setError(e?.response?.data?.detail || "Ошибка ответа собеседника");
    } finally {
      setSending(false);
    }
  };

  const finishAndAnalyze = async () => {
    setFinishing(true);
    setError(null);
    setStatus(null);
    try {
      const conversation = buildTranscript(messages);
      const res = await api.post(`/tests/simulations/${props.scenario}/submit`, { conversation });
      setTaskId(res.data.task_id);
    } catch (e: any) {
      console.error(e);
      setError(e?.response?.data?.detail || "Ошибка отправки симуляции");
    } finally {
      setFinishing(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendUserMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-beige-100">
      <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
        <h1 className="text-2xl font-bold text-brown-800">{props.title}</h1>
        <p className="text-brown-600 text-sm mt-1">{props.subtitle}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-8 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-2xl px-6 py-4 rounded-2xl text-brown-800 text-base leading-relaxed shadow-sm ${
                msg.role === "ai"
                  ? "bg-beige-200 rounded-tl-none"
                  : "bg-white rounded-tr-none border border-beige-300"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {sending ? (
          <div className="flex justify-start">
            <div className="bg-beige-200 px-6 py-4 rounded-2xl rounded-tl-none text-brown-800 text-sm animate-pulse">
              Собеседник печатает...
            </div>
          </div>
        ) : null}

        <div ref={messagesEndRef} />

        {error ? (
          <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
            <div className="text-sm text-red-700">{error}</div>
          </Card>
        ) : null}

        {taskId ? (
          <Card className="bg-white border border-beige-300 shadow-sm rounded-xl p-6">
            <div className="text-lg font-bold text-brown-800">Статус анализа</div>
            <div className="text-brown-600 text-sm mt-2">Task: {taskId}</div>
            <div className="mt-4">
              <div className="inline-flex items-center px-3 py-1 rounded-full bg-beige-200 border border-beige-300 text-xs font-bold text-brown-800">
                {status?.status || "pending"}
              </div>
            </div>

            {status?.status === "completed" && status.result ? (
              <div className="mt-5 space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                  <div className="text-brown-800">
                    Comm: <span className="font-bold">{Math.round(status.result.communication_score)}</span>
                  </div>
                  <div className="text-brown-800">
                    EI: <span className="font-bold">{Math.round(status.result.emotional_intelligence_score)}</span>
                  </div>
                  <div className="text-brown-800">
                    CT: <span className="font-bold">{Math.round(status.result.critical_thinking_score)}</span>
                  </div>
                  <div className="text-brown-800">
                    TM: <span className="font-bold">{Math.round(status.result.time_management_score)}</span>
                  </div>
                  <div className="text-brown-800">
                    Lead: <span className="font-bold">{Math.round(status.result.leadership_score)}</span>
                  </div>
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
      </div>

      <div className="p-8 bg-beige-100 border-t border-beige-300">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Напишите вашу реплику..."
            className="flex-1 bg-beige-200 border border-beige-300 rounded-xl px-4 py-3 text-brown-800 outline-none"
          />
          <Button
            onClick={sendUserMessage}
            disabled={sending || finishing}
            className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
          >
            Отправить
          </Button>
          <Button
            onClick={finishAndAnalyze}
            disabled={!canFinish || sending || finishing}
            className="bg-white hover:bg-beige-200 text-brown-800 border border-beige-300 font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider"
          >
            Завершить
          </Button>
        </div>
      </div>
    </div>
  );
}
