"use client";

import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) return <div className="h-screen w-screen flex items-center justify-center bg-beige-100 text-brown-800">Loading...</div>;
  if (!user) return null;

  return (
    <div className="flex h-screen w-full bg-beige-100">
      <Sidebar />
      <main className="flex-1 overflow-hidden h-full">
        {children}
      </main>
    </div>
  );
}
