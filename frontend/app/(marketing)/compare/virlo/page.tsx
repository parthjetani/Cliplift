import type { Metadata } from "next";
import Link from "next/link";
import { Check, Minus } from "lucide-react";

import { PricingTable } from "@/components/marketing/pricing-table";

export const metadata: Metadata = {
  title: "Cliplift vs Virlo — Why creators are switching",
  description:
    "Flat-rate pricing vs credits, LinkedIn analytics, built-in publishing. See how Cliplift compares to Virlo.ai feature-by-feature.",
  openGraph: {
    title: "Cliplift vs Virlo",
    description:
      "Flat-rate pricing vs credits. LinkedIn coverage. Built-in publishing. See the full comparison.",
  },
};

interface ComparisonRow {
  feature: string;
  cliplift: string | true;
  virlo: string | true | false;
}

const COMPARISON: ComparisonRow[] = [
  { feature: "Pricing model", cliplift: "Flat rate ($29–$149/mo)", virlo: "Credit-based ($49–$199/mo)" },
  { feature: "Unlimited searches", cliplift: true, virlo: "Limited by credits" },
  { feature: "YouTube Shorts tracking", cliplift: true, virlo: true },
  { feature: "Instagram Reels tracking", cliplift: true, virlo: true },
  { feature: "TikTok tracking", cliplift: true, virlo: true },
  { feature: "LinkedIn video tracking", cliplift: true, virlo: false },
  { feature: "Outlier detection (Z-score)", cliplift: true, virlo: true },
  { feature: "AI content briefs", cliplift: true, virlo: false },
  { feature: "Publish directly to platforms", cliplift: true, virlo: false },
  { feature: "Content calendar", cliplift: true, virlo: false },
  { feature: "Multi-user teams", cliplift: "Up to 25 seats", virlo: "Enterprise only" },
  { feature: "API access", cliplift: "Agency plan", virlo: "Enterprise only" },
  { feature: "AI video generation", cliplift: "Phase 2", virlo: "Removed (April 2026)" },
  { feature: "No credits ever", cliplift: true, virlo: false },
];

function CellValue({ value }: { value: string | true | false }) {
  if (value === true) return <Check className="mx-auto h-5 w-5 text-green-600" />;
  if (value === false) return <Minus className="mx-auto h-5 w-5 text-muted-foreground/50" />;
  return <span className="text-sm">{value}</span>;
}

export default function CompareVirloPage() {
  return (
    <div className="container max-w-5xl px-4 py-12 sm:px-6 sm:py-20">
      {/* Hero */}
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">
          Cliplift vs Virlo
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-muted-foreground sm:text-lg">
          Virlo charges credits for every action. Cliplift gives you flat-rate
          unlimited access, LinkedIn analytics, and a built-in publishing loop.
          Here&apos;s the full comparison.
        </p>
      </div>

      {/* Comparison table */}
      <div className="mx-auto mt-12 max-w-3xl overflow-hidden rounded-xl border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 font-medium">Feature</th>
              <th className="px-4 py-3 text-center font-semibold text-primary">
                Cliplift
              </th>
              <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                Virlo
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON.map((row, i) => (
              <tr
                key={row.feature}
                className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}
              >
                <td className="px-4 py-3 font-medium">{row.feature}</td>
                <td className="px-4 py-3 text-center">
                  <CellValue value={row.cliplift} />
                </td>
                <td className="px-4 py-3 text-center">
                  <CellValue value={row.virlo} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Key differentiators */}
      <div className="mx-auto mt-16 grid max-w-4xl grid-cols-1 gap-6 sm:grid-cols-3">
        {[
          {
            title: "No credit anxiety",
            body: "Virlo charges 15 credits to track a creator and 10 per video. Their Starter plan gives 2,000/mo — agencies burn through them in days. Cliplift is flat-rate: track unlimited for one price.",
          },
          {
            title: "LinkedIn coverage",
            body: "Virlo doesn't track LinkedIn video at all. Cliplift is the first short-form analytics tool to include LinkedIn benchmarks, powered by Netrows data.",
          },
          {
            title: "Insight → publish loop",
            body: "Virlo stops at analytics. Cliplift lets you go from outlier detection → AI brief → scheduled post → published video, all without leaving the tool.",
          },
        ].map((d) => (
          <div key={d.title} className="rounded-lg border bg-card p-6">
            <h3 className="font-semibold">{d.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{d.body}</p>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="mx-auto mt-16 max-w-xl text-center">
        <h2 className="text-2xl font-bold">Ready to switch?</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Start a 7-day free trial. No credit card required. Your tracked
          creators and niches are ready in minutes.
        </p>
        <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/register"
            className="rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Start free trial →
          </Link>
          <Link
            href="/discover"
            className="rounded-md border px-6 py-3 text-sm font-medium hover:bg-secondary"
          >
            Try the search first
          </Link>
        </div>
      </div>

      {/* Pricing */}
      <div className="mx-auto mt-16 max-w-5xl sm:mt-24" id="pricing">
        <h2 className="mb-8 text-center text-2xl font-bold">
          Simple, flat-rate pricing
        </h2>
        <PricingTable />
      </div>
    </div>
  );
}
