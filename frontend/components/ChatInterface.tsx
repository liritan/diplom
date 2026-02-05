"use client";

import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/common";
import api from "@/lib/api";
import { VoiceRecorder } from "./VoiceRecorder";

interface Message {
  id: number;
  kind: "text" | "audio";
  text?: string;
  audioUrl?: string;
  audioFetchPath?: string;
  transcript?: string;
  sender: "user" | "ai";
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastVoiceMessageIdRef = useRef<number | null>(null);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await api.get("/chat/me/messages", { params: { limit: 100 } });
        const rows: any[] = Array.isArray(res.data) ? res.data : [];

        if (!rows.length) {
          setMessages([
            {
              id: 1,
              kind: "text",
              text: "👋 Привет! Я ваш AI-тренер по развитию Soft Skills. Чем могу помочь?",
              sender: "ai",
            },
          ]);
          return;
        }

        const audioIds: number[] = [];
        const initialMessages: Message[] = rows.map((m) => {
          const id = typeof m.id === "number" ? m.id : Date.now();
          const hasAudio = Boolean(m.audio_url);
          if (hasAudio && typeof id === "number") audioIds.push(id);

          const transcript =
            hasAudio && typeof m.message === "string" && m.message && m.message !== "(voice)"
              ? m.message
              : undefined;

          return {
            id,
            kind: hasAudio ? ("audio" as const) : ("text" as const),
            text: hasAudio ? undefined : m.message,
            audioUrl: undefined,
            audioFetchPath: hasAudio ? String(m.audio_url) : undefined,
            transcript,
            sender: m.is_user ? ("user" as const) : ("ai" as const),
          };
        });

        setMessages(initialMessages);

        for (const id of audioIds) {
          try {
            const audioRes = await api.get(`/chat/audio/${id}`, { responseType: "blob" });
            const objectUrl = URL.createObjectURL(audioRes.data);
            setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, audioUrl: objectUrl } : msg)));
          } catch (err) {
            console.error(err);
          }
        }
      } catch (e) {
        setMessages([
          {
            id: 1,
            kind: "text",
            text: "👋 Привет! Я ваш AI-тренер по развитию Soft Skills. Чем могу помочь?",
            sender: "ai",
          },
        ]);
      }
    };

    loadHistory();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addTextMessage = (text: string, sender: "user" | "ai") => {
    setMessages((prev) => [...prev, { id: Date.now(), kind: "text", text, sender }]);
  };

  const addAudioMessage = (audioUrl: string, sender: "user" | "ai") => {
    const id = Date.now();
    lastVoiceMessageIdRef.current = id;
    setMessages((prev) => [...prev, { id, kind: "audio", audioUrl, sender }]);
  };

  const attachTranscriptToLastAudio = (text: string) => {
    const id = lastVoiceMessageIdRef.current;
    if (!id) return;
    setMessages((prev) => prev.map((m) => (m.id === id && m.kind === "audio" ? { ...m, transcript: text } : m)));
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const textToSend = input;
    setInput("");
    addTextMessage(textToSend, "user");
    setIsLoading(true);

    try {
      const response = await api.post("/chat/send", { message: textToSend });
      addTextMessage(response.data.response, "ai");
    } catch (error) {
      console.error("Chat error:", error);
      addTextMessage("Извините, произошла ошибка связи с сервером.", "ai");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-beige-100">
      {/* Header */}
      <div className="bg-beige-100 border-b border-beige-300 px-8 py-6">
        <h1 className="text-2xl font-bold text-brown-800">Основной чат</h1>
        <p className="text-brown-600 text-sm mt-1">Общайтесь с AI-тренером для развития мягких навыков</p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-8 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-2xl px-6 py-4 rounded-2xl text-brown-800 text-base leading-relaxed shadow-sm ${
                msg.sender === "ai"
                  ? "bg-beige-200 rounded-tl-none"
                  : "bg-white rounded-tr-none border border-beige-300"
              }`}
            >
              {msg.kind === "audio" ? (
                <div className="space-y-2">
                  {msg.audioUrl ? (
                    <audio controls src={msg.audioUrl} className="w-64" />
                  ) : (
                    "Загрузка аудио..."
                  )}
                </div>
              ) : (
                msg.text
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-beige-200 px-6 py-4 rounded-2xl rounded-tl-none text-brown-800 text-sm animate-pulse">
              AI печатает...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-8 bg-beige-100 border-t border-beige-300">
        <div className="relative flex items-center bg-beige-200 rounded-xl p-2 shadow-inner border border-beige-300 gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Напишите ваше сообщение..."
            className="flex-1 bg-transparent border-none focus:ring-0 text-brown-800 placeholder-brown-400 px-4 py-3 text-base outline-none"
          />
          
          <VoiceRecorder
            onSendText={addTextMessage}
            onSendAudio={addAudioMessage}
            onRecognizedText={attachTranscriptToLastAudio}
          />

          <div className="flex items-center px-2">
            <Button 
                onClick={handleSend} 
                className="bg-accent-button hover:bg-accent-buttonHover text-white font-bold py-2 px-6 rounded-lg uppercase text-xs tracking-wider transition-colors"
            >
              ОТПРАВИТЬ
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
