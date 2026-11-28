import { get } from "svelte/store";
import { accessToken } from "$lib/stores/auth";
import { ApiError, ValidationError } from "./errors";

const BASE_URL = import.meta.env.VITE_API_URL;

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type ValidationItem = { loc: (string | number)[]; msg: string };

function parseFields(body: unknown): Record<string, string> {
  const fields: Record<string, string> = {};
  const detail = (body as { detail?: ValidationItem[] }).detail;
  if (Array.isArray(detail)) {
    for (const item of detail) {
      const name = item.loc.slice(1).join(".") || "non_field";
      fields[name] = item.msg;
    }
  }
  return fields;
}

export async function request<T>(
  method: Method,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const token = get(accessToken);
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status == 401) {
    accessToken.set(null);
    const { navigate } = await import("../../router");
    navigate("/login");
    throw new ApiError(401, "Unauthorized");
  }

  if (res.status == 422) {
    throw new ValidationError(parseFields(await res.json()));
  }

  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const message =
      typeof data?.detail == "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, message);
  }

  if (res.status == 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
