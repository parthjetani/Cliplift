"use client";

import { useCallback, useRef, useState } from "react";
import { Loader2, Upload, Video, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiAuth, ApiError, uploadFileWithProgress } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PresignResponse } from "@/lib/types";

const ACCEPTED_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-m4v",
];

const MAX_SIZE_BYTES = 200 * 1024 * 1024; // 200 MB hard cap for now

export interface UploadedFile {
  file_key: string;
  filename: string;
  size_bytes: number;
  content_type: string;
}

interface UploadDropzoneProps {
  onUploaded: (file: UploadedFile) => void;
  onCleared?: () => void;
  /** Set when a previous upload is already attached (renders the "uploaded" state). */
  uploaded?: UploadedFile | null;
  disabled?: boolean;
}

/**
 * Drag/drop video upload with XHR progress tracking.
 *
 * Two-step flow:
 *   1. POST /publishing/uploads/presign → backend returns { upload_url, file_key }
 *   2. PUT the file directly to upload_url with progress events
 *
 * The bytes never touch FastAPI on the upload path. In dev `upload_url` points
 * at the local PUT sink (`/api/v1/publishing/uploads/local/{file_key}`); in
 * prod it points at a Supabase Storage signed URL.
 */
export function UploadDropzone({
  onUploaded,
  onCleared,
  uploaded,
  disabled = false,
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError(
          `Unsupported file type. Allowed: ${ACCEPTED_TYPES.map((t) => t.replace("video/", ".")).join(", ")}`
        );
        return;
      }
      if (file.size > MAX_SIZE_BYTES) {
        setError(
          `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 200 MB.`
        );
        return;
      }

      setIsUploading(true);
      setProgress(0);

      try {
        // Step 1 — request a presigned upload URL
        const presign = await apiAuth<PresignResponse>(
          "/api/v1/publishing/uploads/presign",
          {
            method: "POST",
            body: { filename: file.name, content_type: file.type },
          }
        );

        // Step 2 — PUT bytes directly to the storage backend
        await uploadFileWithProgress(presign.upload_url, file, (p) =>
          setProgress(p.percent)
        );

        onUploaded({
          file_key: presign.file_key,
          filename: file.name,
          size_bytes: file.size,
          content_type: file.type,
        });
      } catch (e) {
        const msg =
          e instanceof ApiError ? e.message : "Upload failed";
        setError(msg);
      } finally {
        setIsUploading(false);
      }
    },
    [onUploaded]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled || isUploading) return;
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [disabled, isUploading, handleFile]
  );

  const onSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Allow re-selecting the same file
      e.target.value = "";
    },
    [handleFile]
  );

  // Uploaded state
  if (uploaded) {
    return (
      <div className="rounded-md border border-border bg-card p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-primary/10 p-2">
            <Video className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 space-y-1">
            <p className="line-clamp-1 text-sm font-medium">
              {uploaded.filename}
            </p>
            <p className="text-xs text-muted-foreground">
              {(uploaded.size_bytes / 1024 / 1024).toFixed(1)} MB · uploaded
            </p>
          </div>
          {onCleared && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onCleared}
              disabled={disabled}
              aria-label="Remove uploaded file"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Uploading state
  if (isUploading) {
    return (
      <div className="rounded-md border border-border bg-card p-6">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Loader2 className="h-4 w-4 animate-spin" />
            Uploading… {progress}%
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-all duration-150"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  // Idle / dropzone state
  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-8 text-center transition",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-foreground/50",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <Upload className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">
          Drop a video here or click to browse
        </p>
        <p className="text-xs text-muted-foreground">
          MP4, MOV, or WebM · max 200 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          onChange={onSelect}
          className="hidden"
          disabled={disabled}
        />
      </div>
      {error && (
        <div className="mt-2 rounded-md border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive">
          {error}
        </div>
      )}
    </div>
  );
}
