"use client";

import { useEffect, useState, useTransition } from "react";
import { Copy, Lightbulb, Loader2, Sparkles, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { apiAuth, ApiError } from "@/lib/api";
import type { ContentBrief, GenerateIdeaResponse } from "@/lib/types";

interface ContentBriefDialogProps {
  videoId: string;
  videoTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ContentBriefDialog({
  videoId,
  videoTitle,
  open,
  onOpenChange,
}: ContentBriefDialogProps) {
  const [brief, setBrief] = useState<ContentBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const generate = () => {
    setError(null);
    startTransition(async () => {
      try {
        const result = await apiAuth<GenerateIdeaResponse>(
          "/api/v1/discover/generate-idea",
          {
            method: "POST",
            body: { video_id: videoId },
          }
        );
        setBrief(result.brief);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(
            err.code === "rate_limited"
              ? "Rate limit reached (10/hour). Try again later."
              : err.message
          );
        } else {
          setError("Failed to generate content brief");
        }
      }
    });
  };

  // Auto-generate when the dialog opens. We use useEffect rather than relying
  // on Radix's onOpenChange callback because the parent (`ContentBriefButton`)
  // controls `open` externally via `setOpen(true)` — Radix only fires
  // onOpenChange for its own internal state transitions (trigger click, Esc),
  // not for controlled-prop changes from the parent. Without this effect, the
  // modal opens but the brief is never fetched and the body stays empty.
  useEffect(() => {
    if (open && !brief && !isPending && !error) {
      generate();
    }
    // We intentionally only depend on `open` — generate() reads videoId via
    // closure and the other guards prevent re-fires on re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Content Brief
          </DialogTitle>
          <DialogDescription className="line-clamp-1">
            Based on: {videoTitle}
          </DialogDescription>
        </DialogHeader>

        {isPending && (
          <div className="flex flex-col items-center py-12">
            <Loader2 className="mb-3 h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Analyzing the video...
            </p>
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {brief && !isPending && (
          <div className="space-y-4">
            {brief.cached && (
              <Badge variant="secondary" className="text-xs">
                Cached result
              </Badge>
            )}

            <BriefSection
              label="Hook analysis"
              icon={<Lightbulb className="h-4 w-4" />}
              content={brief.hook_analysis}
            />

            <BriefSection
              label="Format"
              content={brief.format}
            />

            <BriefSection
              label="Suggested hook"
              content={brief.suggested_hook}
              copyable
              onCopy={() =>
                copyToClipboard(brief.suggested_hook, "hook")
              }
              copied={copiedField === "hook"}
            />

            <BriefSection
              label="Suggested caption"
              content={brief.suggested_caption}
              copyable
              onCopy={() =>
                copyToClipboard(brief.suggested_caption, "caption")
              }
              copied={copiedField === "caption"}
            />

            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Hashtags
              </p>
              <div className="flex flex-wrap gap-1">
                {brief.suggested_hashtags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="outline"
                    className="cursor-pointer text-xs hover:bg-secondary"
                    onClick={() => copyToClipboard(`#${tag}`, `tag-${tag}`)}
                  >
                    #{tag}
                    {copiedField === `tag-${tag}` && (
                      <Check className="ml-1 h-3 w-3" />
                    )}
                  </Badge>
                ))}
              </div>
            </div>

            <BriefSection
              label="Call to action"
              content={brief.cta}
              copyable
              onCopy={() => copyToClipboard(brief.cta, "cta")}
              copied={copiedField === "cta"}
            />

            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() =>
                copyToClipboard(
                  `${brief.suggested_hook}\n\n${brief.suggested_caption}\n\n${brief.suggested_hashtags.map((t) => `#${t}`).join(" ")}\n\n${brief.cta}`,
                  "all"
                )
              }
            >
              {copiedField === "all" ? (
                <>
                  <Check className="h-4 w-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy full brief
                </>
              )}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function BriefSection({
  label,
  content,
  icon,
  copyable,
  onCopy,
  copied,
}: {
  label: string;
  content: string;
  icon?: React.ReactNode;
  copyable?: boolean;
  onCopy?: () => void;
  copied?: boolean;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5">
        {icon}
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {copyable && onCopy && (
          <button
            onClick={onCopy}
            className="ml-auto text-muted-foreground hover:text-foreground"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-600" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </button>
        )}
      </div>
      <p className="text-sm">{content}</p>
    </div>
  );
}
