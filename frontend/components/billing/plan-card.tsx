"use client";

import { Check, Loader2 } from "lucide-react";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiAuth, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CheckoutSessionResponse } from "@/lib/types";

interface PlanCardProps {
  name: string;
  monthlyPrice: number;
  features: string[];
  isCurrent: boolean;
  planKey: "creator" | "team" | "agency";
  highlighted?: boolean;
}

export function PlanCard({
  name,
  monthlyPrice,
  features,
  isCurrent,
  planKey,
  highlighted = false,
}: PlanCardProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleUpgrade = () => {
    setError(null);
    startTransition(async () => {
      try {
        const resp = await apiAuth<CheckoutSessionResponse>(
          "/api/v1/billing/checkout",
          {
            method: "POST",
            body: { plan: planKey, billing_period: "monthly" },
          }
        );
        window.location.href = resp.checkout_url;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to start checkout");
      }
    });
  };

  return (
    <Card
      className={cn(
        "relative flex flex-col",
        highlighted && "ring-2 ring-primary"
      )}
    >
      {highlighted && (
        <Badge className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground">
          Popular
        </Badge>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{name}</CardTitle>
        <div className="mt-1">
          <span className="text-3xl font-bold">${monthlyPrice}</span>
          <span className="text-sm text-muted-foreground">/mo</span>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4">
        <ul className="space-y-2 text-sm">
          {features.map((f) => (
            <li key={f} className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-teal-600" />
              <span>{f}</span>
            </li>
          ))}
        </ul>

        {isCurrent ? (
          <Button variant="outline" disabled className="w-full">
            Current plan
          </Button>
        ) : (
          <Button
            className="w-full"
            variant={highlighted ? "default" : "outline"}
            onClick={handleUpgrade}
            disabled={isPending}
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Redirecting...
              </>
            ) : (
              `Upgrade to ${name}`
            )}
          </Button>
        )}
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </CardContent>
    </Card>
  );
}
