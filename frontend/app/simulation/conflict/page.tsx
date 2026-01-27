"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationConflictPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="conflict"
        title="Конфликт в команде"
        subtitle="Потренируйтесь вести сложный разговор и снижать напряжение"
        systemIntro="Привет. Меня очень задело, как ты поступил в этой ситуации. Давай обсудим."
      />
    </AppLayout>
  );
}
