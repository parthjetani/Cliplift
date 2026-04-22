/**
 * Backend API client.
 *
 * Wraps `fetch` to:
 * - Prepend NEXT_PUBLIC_API_URL
 * - Attach the Supabase JWT to authenticated requests
 * - Handle the standard error envelope { error: { code, message, details? } }
 *
 * Two flavors:
 * - `apiPublic(...)` — no auth, used for /discover/search etc.
 * - `apiAuth(...)`   — attaches Bearer token from the current Supabase session
 */

import { toast } from "sonner";

import { createClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function request<T>(
  path: string,
  options: ApiOptions & { token?: string | null } = {}
): Promise<T> {
  const { method = "GET", body, headers = {}, signal, token } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };
  if (token) {
    finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!response.ok) {
    let errorBody: { error?: { code?: string; message?: string; details?: unknown } } = {};
    try {
      errorBody = await response.json();
    } catch {
      // Non-JSON error response
    }
    throw new ApiError(
      response.status,
      errorBody.error?.code || "unknown_error",
      errorBody.error?.message || response.statusText,
      errorBody.error?.details
    );
  }

  // Handle empty 204 responses
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/** Make an API call without authentication (e.g., public discover/search). */
export async function apiPublic<T>(path: string, options: ApiOptions = {}): Promise<T> {
  return request<T>(path, options);
}

/** Make an authenticated API call — attaches Supabase JWT from the current session. */
export async function apiAuth<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new ApiError(401, "unauthorized", "Not signed in");
  }

  return request<T>(path, { ...options, token: session.access_token });
}

/**
 * Show a toast for API errors. Call from `.catch()` blocks where you want
 * global error visibility in addition to local error state.
 *
 * 402 → upgrade CTA; 429 → slow-down message; 500 → generic.
 */
export function showApiError(err: unknown): void {
  if (!(err instanceof ApiError)) {
    toast.error("Something went wrong");
    return;
  }
  if (err.status === 402) {
    const details = err.details as { limit_name?: string; suggested_plan?: string } | undefined;
    const plan = details?.suggested_plan || "a higher plan";
    toast.error(err.message, {
      action: {
        label: "Upgrade",
        onClick: () => {
          window.location.href = "/dashboard/settings/billing";
        },
      },
      duration: 8000,
    });
    return;
  }
  if (err.status === 429) {
    toast.warning("Slow down — you've hit a rate limit. Try again in a minute.");
    return;
  }
  if (err.status >= 500) {
    toast.error("Server error. Please try again later.");
    return;
  }
  toast.error(err.message);
}

/**
 * PUT a binary file to a presigned upload URL with progress events.
 *
 * `fetch()` has no upload-progress events, so this uses XMLHttpRequest. Used
 * by the post composer's drag-drop dropzone — backend's presign endpoint
 * returns the URL, the browser PUTs straight to storage, the backend never
 * sees the bytes.
 */
export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export function uploadFileWithProgress(
  uploadUrl: string,
  file: File,
  onProgress?: (progress: UploadProgress) => void,
  signal?: AbortSignal
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    if (onProgress) {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          onProgress({
            loaded: e.loaded,
            total: e.total,
            percent: Math.round((e.loaded / e.total) * 100),
          });
        }
      });
    }

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(
          new ApiError(
            xhr.status,
            "upload_failed",
            `Upload failed: ${xhr.statusText || xhr.status}`
          )
        );
      }
    });

    xhr.addEventListener("error", () => {
      reject(new ApiError(0, "network_error", "Network error during upload"));
    });

    xhr.addEventListener("abort", () => {
      reject(new ApiError(0, "aborted", "Upload aborted"));
    });

    if (signal) {
      signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.send(file);
  });
}
