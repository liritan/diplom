"use client";

import { useForm } from "react-hook-form";
import { useAuth } from "@/context/AuthContext";
import { Button, Input, Card } from "@/components/ui/common";
import { useState } from "react";
import api from "@/lib/api";
import Link from "next/link";

export default function LoginPage() {
  const { register, handleSubmit } = useForm();
  const { login } = useAuth();
  const [error, setError] = useState("");

  const onSubmit = async (data: any) => {
    try {
      // API expects form data for OAuth2
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password);
      
      const response = await api.post("/auth/login", formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
      });
      login(response.data.access_token);
    } catch (err) {
      setError("Invalid email or password");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-beige-100">
      <Card className="w-full max-w-md space-y-8 bg-white border border-beige-300 rounded-xl p-8 shadow-sm">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-brown-800">Sign in</h2>
          <p className="mt-2 text-sm text-brown-600">
            Or <Link href="/register" className="text-brown-600 hover:text-brown-800 underline">create a new account</Link>
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="-space-y-px rounded-md shadow-sm">
            <div className="mb-4">
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
              Sign in
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
