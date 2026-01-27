"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationNegotiationPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="negotiation"
        title="Переговоры"
        subtitle="Потренируйтесь договариваться и аргументировать в формате чата"
        systemIntro="Здравствуйте! Давайте обсудим условия. Что для вас сейчас самое важное в этой сделке?"
      />
    </AppLayout>
  );
}
