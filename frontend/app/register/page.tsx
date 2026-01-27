"use client";

import { useForm } from "react-hook-form";
import { Button, Input, Card } from "@/components/ui/common";
import { useState } from "react";
import api from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function RegisterPage() {
  const { register, handleSubmit } = useForm();
  const router = useRouter();
  const [error, setError] = useState("");

  const onSubmit = async (data: any) => {
    try {
      await api.post("/auth/register", {
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        role: "user"
      });
      router.push("/login");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-beige-100">
      <Card className="w-full max-w-md space-y-8 bg-white border border-beige-300 rounded-xl p-8 shadow-sm">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-brown-800">Create Account</h2>
          <p className="mt-2 text-sm text-brown-600">
            Already have an account? <Link href="/login" className="text-brown-600 hover:text-brown-800 underline">Sign in</Link>
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4 rounded-md shadow-sm">
            <div>
              <Input
                {...register("full_name", { required: true })}
                type="text"
                placeholder="Full Name"
                className="relative block w-full appearance-none rounded-md border border-beige-300 px-3 py-2 text-brown-800 placeholder-brown-600/70 focus:z-10 focus:border-brown-600 focus:outline-none focus:ring-brown-600 sm:text-sm"
              />
            </div>
            <div>
              <Input
                {...register("email", { required: true })}
                type="email"
                placeholder="Email address"
                className="relative block w-full appearance-none rounded-md border border-beige-300 px-3 py-2 text-brown-800 placeholder-brown-600/70 focus:z-10 focus:border-brown-600 focus:outline-none focus:ring-brown-600 sm:text-sm"
              />
            </div>
            <div>
              <Input
                {...register("password", { required: true })}
                type="password"
                placeholder="Password"
                className="relative block w-full appearance-none rounded-md border border-beige-300 px-3 py-2 text-brown-800 placeholder-brown-600/70 focus:z-10 focus:border-brown-600 focus:outline-none focus:ring-brown-600 sm:text-sm"
              />
            </div>
          </div>

          {error && <div className="text-red-500 text-sm text-center">{error}</div>}

          <div>
            <Button type="submit" className="w-full">
              Register
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
