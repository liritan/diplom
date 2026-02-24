"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationTimeManagementPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="time-management"
        title="Планирование и дедлайны"
        subtitle="Потренируйтесь управлять временем, приоритетами и сроками"
        systemIntro="Ситуация: у команды несколько критичных задач и близкий дедлайн. Какой план действий вы предложите?"
      />
    </AppLayout>
  );
}
