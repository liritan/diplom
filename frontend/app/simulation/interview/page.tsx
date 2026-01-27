"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationInterviewPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="interview"
        title="Собеседование"
        subtitle="Потренируйтесь отвечать на вопросы интервьюера в формате чата"
        systemIntro="Здравствуйте! Давайте начнём собеседование. Расскажите немного о себе."
      />
    </AppLayout>
  );
}
