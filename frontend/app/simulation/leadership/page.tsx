"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationLeadershipPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="leadership"
        title="Р›РёРґРµСЂСЃС‚РІРѕ РІ РєРѕРјР°РЅРґРµ"
        subtitle="РџРѕС‚СЂРµРЅРёСЂСѓР№С‚РµСЃСЊ РІРµСЃС‚Рё РєРѕРјР°РЅРґСѓ РІ СЃР»РѕР¶РЅРѕР№ СЂР°Р±РѕС‡РµР№ СЃРёС‚СѓР°С†РёРё"
        systemIntro="Р’Р°С€Р° РєРѕРјР°РЅРґР° РїРѕС‚РµСЂСЏР»Р° С„РѕРєСѓСЃ Рё СЂРёСЃРєСѓРµС‚ РЅРµ СѓСЃРїРµС‚СЊ Рє СЂРµР»РёР·Сѓ. РљР°Рє РІС‹ РІРѕР·СЊРјРµС‚Рµ Р»РёРґРµСЂСЃС‚РІРѕ Рё РѕСЂРіР°РЅРёР·СѓРµС‚Рµ СЂР°Р±РѕС‚Сѓ?"
      />
    </AppLayout>
  );
}
