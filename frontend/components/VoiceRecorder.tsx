"use client";

import { useState, useRef } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/common";
import api from "@/lib/api";

function writeString(view: DataView, offset: number, value: string) {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}

function encodeWav(samples: Float32Array, sampleRate: number) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");

  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);

  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    let s = samples[i];
    if (s > 1) s = 1;
    if (s < -1) s = -1;
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return buffer;
}

async function convertToWav16kMono(blob: Blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
  const audioCtx = new AudioCtx();
  const decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
  await audioCtx.close();

  const targetSampleRate = 16000;
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * targetSampleRate), targetSampleRate);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start(0);
  const rendered = await offline.startRendering();

  const samples = rendered.getChannelData(0);
  const wavBuffer = encodeWav(samples, rendered.sampleRate);
  return new Blob([wavBuffer], { type: "audio/wav" });
}

interface VoiceRecorderProps {
  onSendText: (text: string, sender: "user" | "ai") => void;
  onSendAudio: (audioUrl: string, sender: "user" | "ai") => void;
  uploadPath?: string;
  extraFormFields?: Record<string, string>;
  onRecognizedText?: (text: string) => void;
}

export function VoiceRecorder({ onSendText, onSendAudio, uploadPath, extraFormFields, onRecognizedText }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredTypes = ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm"];
      const mimeType = preferredTypes.find((t) => MediaRecorder.isTypeSupported(t));
      const mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        const recordedMime = mediaRecorder.mimeType || "audio/webm";
        const audioBlob = new Blob(chunksRef.current, { type: recordedMime });
        const audioUrl = URL.createObjectURL(audioBlob);
        onSendAudio(audioUrl, "user");
        const formData = new FormData();

        let uploadBlob: Blob = audioBlob;
        let uploadName = recordedMime.includes("ogg") ? "voice_message.ogg" : "voice_message.webm";
        if (!recordedMime.includes("ogg")) {
          try {
            uploadBlob = await convertToWav16kMono(audioBlob);
            uploadName = "voice_message.wav";
          } catch (e) {
            console.error(e);
          }
        }

        formData.append("file", uploadBlob, uploadName);

        if (extraFormFields) {
          for (const [k, v] of Object.entries(extraFormFields)) {
            formData.append(k, v);
          }
        }

        try {
          // Optimistically show "Audio message sending..." or similar if needed
          // For now we wait for server to return the transcribed text or response
          
          // Note: Backend /chat/voice returns { response: "AI response" }
          // But it also performs STT. Ideally we might want the user's transcribed text too.
          // For this MVP, we will just display the AI's response to the voice message.
          // Or we can assume the backend returns the transcribed text too if we modify it.
          // Let's modify backend to return { user_text: "...", response: "..." } for better UX.
          
          const res = await api.post(uploadPath || "/chat/voice", formData, {
            headers: { "Content-Type": "multipart/form-data" },
          });

          if (res.data?.user_text && onRecognizedText) {
            onRecognizedText(String(res.data.user_text));
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
