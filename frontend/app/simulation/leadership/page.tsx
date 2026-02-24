"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationLeadershipPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="leadership"
        title="Лидерство в команде"
        subtitle="Потренируйтесь вести команду в сложной рабочей ситуации"
        systemIntro="Ваша команда потеряла фокус и рискует не успеть к релизу. Как вы возьмете лидерство и организуете работу?"
      />
    </AppLayout>
  );
}
