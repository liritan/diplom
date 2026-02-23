"use client";

import AppLayout from "@/components/AppLayout";
import { SimulationChat } from "@/components/SimulationChat";

export default function SimulationTimeManagementPage() {
  return (
    <AppLayout>
      <SimulationChat
        scenario="time-management"
        title="РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ Рё РґРµРґР»Р°Р№РЅС‹"
        subtitle="РџРѕС‚СЂРµРЅРёСЂСѓР№С‚РµСЃСЊ СѓРїСЂР°РІР»СЏС‚СЊ РІСЂРµРјРµРЅРµРј, РїСЂРёРѕСЂРёС‚РµС‚Р°РјРё Рё СЃСЂРѕРєР°РјРё"
        systemIntro="РЎРёС‚СѓР°С†РёСЏ: Сѓ РєРѕРјР°РЅРґС‹ РЅРµСЃРєРѕР»СЊРєРѕ РєСЂРёС‚РёС‡РЅС‹С… Р·Р°РґР°С‡ Рё Р±Р»РёР·РєРёР№ РґРµРґР»Р°Р№РЅ. РљР°РєРѕР№ РїР»Р°РЅ РґРµР№СЃС‚РІРёР№ РІС‹ РїСЂРµРґР»РѕР¶РёС‚Рµ?"
      />
    </AppLayout>
  );
}
