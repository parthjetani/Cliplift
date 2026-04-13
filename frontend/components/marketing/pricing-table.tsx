import Link from "next/link";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface PlanColumn {
  name: string;
  price: number;
  period: string;
  tagline: string;
  features: string[];
  highlighted?: boolean;
  cta: string;
  href: string;
}

const PLANS: PlanColumn[] = [
  {
    name: "Creator",
    price: 29,
    period: "/mo",
    tagline: "For individual creators getting started.",
    features: [
      "Unlimited trend searches",
      "3 tracked creators",
      "1 platform (YouTube or Instagram)",
      "Outlier detection + AI briefs",
      "1 user",
    ],
    cta: "Start free trial",
    href: "/register",
  },
  {
    name: "Team",
    price: 79,
    period: "/mo",
    tagline: "For growth teams shipping daily.",
    highlighted: true,
    features: [
      "Everything in Creator",
      "25 tracked creators",
      "All 4 platforms",
      "Post scheduling + calendar",
      "50 AI briefs / hour",
      "Up to 5 team members",
    ],
    cta: "Start free trial",
    href: "/register",
  },
  {
    name: "Agency",
    price: 149,
    period: "/mo",
    tagline: "For agencies managing multiple brands.",
    features: [
      "Everything in Team",
      "50 tracked creators",
      "Unlimited AI briefs",
      "API access",
      "25 team members",
      "White-label reports",
    ],
    cta: "Start free trial",
    href: "/register",
  },
];

/**
 * Reusable pricing table — rendered on the landing page and referenced
 * from the billing settings page. Stateless, no API calls.
 */
export function PricingTable() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-6">
      {PLANS.map((plan) => (
        <div
          key={plan.name}
          className={cn(
            "relative flex flex-col rounded-xl border bg-card p-6",
            plan.highlighted && "ring-2 ring-primary"
          )}
        >
          {plan.highlighted && (
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
              Most popular
            </span>
          )}
          <div>
            <h3 className="text-lg font-semibold">{plan.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{plan.tagline}</p>
            <div className="mt-4">
              <span className="text-4xl font-bold">${plan.price}</span>
              <span className="text-muted-foreground">{plan.period}</span>
            </div>
          </div>

          <ul className="mt-6 flex-1 space-y-3 text-sm">
            {plan.features.map((f) => (
              <li key={f} className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                <span>{f}</span>
              </li>
            ))}
          </ul>

          <Link
            href={plan.href}
            className={cn(
              "mt-6 block rounded-md px-4 py-2.5 text-center text-sm font-medium transition",
              plan.highlighted
                ? "bg-primary text-primary-foreground hover:opacity-90"
                : "border border-border hover:bg-secondary"
            )}
          >
            {plan.cta}
          </Link>
        </div>
      ))}

      <p className="col-span-full mt-2 text-center text-xs text-muted-foreground">
        All plans include a 7-day free trial. Annual billing saves 30%. No
        credits, ever.
      </p>
    </div>
  );
}
