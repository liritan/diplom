"use client";

import { useState, useRef } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/common";
import api from "@/lib/api";

interface VoiceRecorderProps {
  onSendText: (text: string, sender: "user" | "ai") => void;
  onSendAudio: (audioUrl: string, sender: "user" | "ai") => void;
}

export function VoiceRecorder({ onSendText, onSendAudio }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        const audioUrl = URL.createObjectURL(audioBlob);
        onSendAudio(audioUrl, "user");
        const formData = new FormData();
        formData.append("file", audioBlob, "voice_message.webm");

        try {
          // Optimistically show "Audio message sending..." or similar if needed
          // For now we wait for server to return the transcribed text or response
          
          // Note: Backend /chat/voice returns { response: "AI response" }
          // But it also performs STT. Ideally we might want the user's transcribed text too.
          // For this MVP, we will just display the AI's response to the voice message.
          // Or we can assume the backend returns the transcribed text too if we modify it.
          // Let's modify backend to return { user_text: "...", response: "..." } for better UX.
          
          const res = await api.post("/chat/voice", formData, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          
          // Assuming backend now returns { user_text, response }
          if (res.data.user_text) {
             onSendText(res.data.user_text, "user");
          }
          
          if (res.data.response) {
            onSendText(res.data.response, "ai");
          }

        } catch (error) {
          console.error("Voice upload error", error);
          onSendText("Ошибка обработки голосового сообщения", "ai");
        } finally {
          setIsProcessing(false);
          stream.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone", err);
      alert("Не удалось получить доступ к микрофону");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="flex items-center">
      {isProcessing ? (
        <Button disabled className="bg-beige-300 text-brown-800 p-3 rounded-full">
          <Loader2 className="w-5 h-5 animate-spin" />
        </Button>
      ) : isRecording ? (
        <Button 
          onClick={stopRecording}
          className="bg-red-500 hover:bg-red-600 text-white p-3 rounded-full animate-pulse shadow-md"
        >
          <Square className="w-5 h-5 fill-current" />
        </Button>
      ) : (
        <Button 
          onClick={startRecording}
          className="bg-white hover:bg-beige-200 text-brown-600 border border-beige-300 p-3 rounded-full shadow-sm transition-colors"
          title="Записать голосовое сообщение"
        >
          <Mic className="w-5 h-5" />
        </Button>
      )}
    </div>
  );
}
