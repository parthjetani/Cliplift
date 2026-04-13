"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PostStatus, ScheduledPostResponse } from "@/lib/types";

interface ContentCalendarProps {
  posts: ScheduledPostResponse[];
}

const statusDot: Record<PostStatus, string> = {
  draft: "bg-slate-400",
  scheduled: "bg-blue-500",
  publishing: "bg-amber-500 animate-pulse",
  published: "bg-green-500",
  failed: "bg-red-500",
};

/**
 * Read-only month grid of scheduled posts. Each cell shows up to 3 post pills
 * colored by status, with a "+N more" overflow link. Drag-to-reschedule is
 * deferred to Phase 2 — users edit `scheduled_for` via the post detail page.
 */
export function ContentCalendar({ posts }: ContentCalendarProps) {
  const [cursor, setCursor] = useState(new Date());

  // Build a list of every day in the visible 6-week window for the current month
  const days = useMemo(() => {
    const monthStart = startOfMonth(cursor);
    const monthEnd = endOfMonth(cursor);
    const gridStart = startOfWeek(monthStart, { weekStartsOn: 0 });
    const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 0 });
    return eachDayOfInterval({ start: gridStart, end: gridEnd });
  }, [cursor]);

  // Group posts by day key (YYYY-MM-DD)
  const postsByDay = useMemo(() => {
    const map = new Map<string, ScheduledPostResponse[]>();
    for (const post of posts) {
      const key = format(new Date(post.scheduled_for), "yyyy-MM-dd");
      const list = map.get(key) ?? [];
      list.push(post);
      map.set(key, list);
    }
    return map;
  }, [posts]);

  const today = new Date();

  return (
    <Card>
      <CardContent className="p-4 sm:p-6">
        {/* Month nav */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {format(cursor, "MMMM yyyy")}
          </h2>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setCursor(subMonths(cursor, 1))}
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCursor(new Date())}
            >
              Today
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setCursor(addMonths(cursor, 1))}
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Weekday headers */}
        <div className="mb-1 grid grid-cols-7 gap-1 text-center text-xs font-medium text-muted-foreground">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
            <div key={d} className="py-1">
              {d}
            </div>
          ))}
        </div>

        {/* Day grid */}
        <div className="grid grid-cols-7 gap-1">
          {days.map((day) => {
            const dayKey = format(day, "yyyy-MM-dd");
            const dayPosts = postsByDay.get(dayKey) ?? [];
            const inCurrentMonth = isSameMonth(day, cursor);
            const isToday = isSameDay(day, today);
            const visiblePosts = dayPosts.slice(0, 3);
            const overflowCount = dayPosts.length - visiblePosts.length;

            return (
              <div
                key={dayKey}
                className={cn(
                  "min-h-[80px] rounded-md border p-1 text-left transition-colors",
                  inCurrentMonth
                    ? "bg-background hover:bg-muted/50"
                    : "bg-muted/30 text-muted-foreground",
                  isToday && "ring-2 ring-primary"
                )}
              >
                <div
                  className={cn(
                    "mb-1 text-xs font-medium",
                    isToday && "text-primary"
                  )}
                >
                  {format(day, "d")}
                </div>
                <div className="space-y-1">
                  {visiblePosts.map((post) => (
                    <Link
                      key={post.id}
                      href={`/dashboard/posts/${post.id}`}
                      className="block rounded px-1.5 py-0.5 text-[10px] font-medium leading-tight hover:bg-secondary"
                      title={post.title || "(untitled)"}
                    >
                      <span className="flex items-center gap-1">
                        <span
                          className={cn(
                            "h-1.5 w-1.5 shrink-0 rounded-full",
                            statusDot[post.status]
                          )}
                        />
                        <span className="truncate">
                          {post.title || "(untitled)"}
                        </span>
                      </span>
                    </Link>
                  ))}
                  {overflowCount > 0 && (
                    <Link
                      href={`/dashboard/posts?date=${dayKey}`}
                      className="block px-1.5 text-[10px] font-medium text-primary hover:underline"
                    >
                      +{overflowCount} more
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          {(
            ["scheduled", "publishing", "published", "failed", "draft"] as PostStatus[]
          ).map((s) => (
            <span key={s} className="flex items-center gap-1.5">
              <span
                className={cn("h-2 w-2 rounded-full", statusDot[s])}
              />
              {s}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
