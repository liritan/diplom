"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/components/ui/common";
import { useAuth } from "@/context/AuthContext";
import { MessageSquare, BarChart2, PieChart, FileText, BookOpen, Award, History, Users, MessageCircle, Mic } from "lucide-react";

const menuItems = [
  {
    category: "РћРЎРќРћР’РќРћР•",
    items: [
      { name: "РћСЃРЅРѕРІРЅРѕР№ С‡Р°С‚", icon: MessageSquare, href: "/chat" },
      { name: "РђРЅР°Р»РёР· РЅР°РІС‹РєРѕРІ", icon: PieChart, href: "/analysis" },
      { name: "РЎС‚Р°С‚РёСЃС‚РёРєР°", icon: BarChart2, href: "/dashboard" },
    ],
  },
  {
    category: "РўР Р•РќРРќР“Р Р РўР•РЎРўР«",
    items: [
      { name: "РўРµСЃС‚С‹", icon: FileText, href: "/tests" },
      { name: "РњР°С‚РµСЂРёР°Р»С‹", icon: BookOpen, href: "/materials" },
      { name: "Р”РѕСЃС‚РёР¶РµРЅРёСЏ", icon: Award, href: "/achievements" },
      { name: "РСЃС‚РѕСЂРёСЏ", icon: History, href: "/history" },
    ],
  },
  {
    category: "Р РћР›Р•Р’Р«Р• РР“Р Р«",
    items: [
      { name: "Р’СЃРµ СЂРѕР»РµРІС‹Рµ РёРіСЂС‹", icon: Users, href: "/simulation" },
      { name: "РЎРѕР±РµСЃРµРґРѕРІР°РЅРёРµ", icon: Users, href: "/simulation/interview" },
      { name: "РљРѕРЅС„Р»РёРєС‚ РІ РєРѕРјР°РЅРґРµ", icon: MessageCircle, href: "/simulation/conflict" },
      { name: "РџРµСЂРµРіРѕРІРѕСЂС‹", icon: Mic, href: "/simulation/negotiation" },
      { name: "Тайм-менеджмент", icon: Mic, href: "/simulation/time-management" },
      { name: "Лидерство", icon: Users, href: "/simulation/leadership" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  const items = user?.role === "admin"
    ? [
        ...menuItems,
        {
          category: "РђР”РњРРќ",
          items: [
            { name: "РђРґРјРёРЅ-РїР°РЅРµР»СЊ", icon: Users, href: "/admin" },
          ],
        },
      ]
    : menuItems;

  return (
    <aside className="w-64 bg-beige-200 h-screen flex flex-col border-r border-beige-300">
      <div className="h-16 flex items-center px-6 bg-accent-gold text-white font-bold text-xl tracking-wide shadow-sm">
        AI РўСЂРµРЅРµСЂ
      </div>
      
      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-8">
        {items.map((section, idx) => (
          <div key={idx}>
            <h3 className="text-xs font-bold text-brown-600 uppercase tracking-wider mb-3 px-2">
              {section.category}
            </h3>
            <ul className="space-y-1">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center px-4 py-2.5 rounded-lg text-sm font-medium transition-colors",
                        isActive
                          ? "bg-white text-brown-800 shadow-sm"
                          : "text-brown-800 hover:bg-white/50 hover:text-brown-800"
                      )}
                    >
                      {/* <item.icon className="w-4 h-4 mr-3 opacity-70" />  -- Icon removed to match design strictly if needed, but kept for usability */}
                      <span>{item.name}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}

