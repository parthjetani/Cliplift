import Link from "next/link";
import {
  Search,
  Sparkles,
  CalendarPlus,
  BarChart3,
  ChevronDown,
  Quote,
} from "lucide-react";
import { PricingTable } from "@/components/marketing/pricing-table";

export default function HomePage() {
  return (
    <div className="px-4 py-12 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-3xl text-center">
        <div className="mb-4 inline-flex items-center rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
          The anti-credit alternative to Virlo
        </div>

        <h1 className="text-balance text-3xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Discover what&apos;s going viral.
          <br />
          <span className="text-muted-foreground">Publish your response.</span>
        </h1>

        <p className="mx-auto mt-4 max-w-2xl text-balance text-base text-muted-foreground sm:mt-6 sm:text-lg">
          Track short-form trends across YouTube, Instagram, LinkedIn, and TikTok.
          Schedule posts, measure results, and find outliers before they peak.
          One tool, flat rate,{" "}
          <span className="font-semibold text-foreground">no credits.</span>
        </p>

        <div className="mt-8 flex flex-col items-center gap-3 sm:mt-10 sm:flex-row sm:justify-center sm:gap-4">
          <Link
            href="/discover"
            className="w-full rounded-md bg-primary px-6 py-3 text-center text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 sm:w-auto"
          >
            Try the search →
          </Link>
          <Link
            href="/register"
            className="w-full rounded-md border border-border px-6 py-3 text-center text-sm font-medium transition hover:bg-secondary sm:w-auto"
          >
            Create account
          </Link>
        </div>

        <p className="mt-4 text-sm text-muted-foreground sm:mt-6">
          No login required to search. Start tracking from $29/mo.
        </p>
      </div>

      {/* Feature grid */}
      <div className="mx-auto mt-12 grid w-full max-w-4xl grid-cols-1 gap-4 sm:mt-24 sm:grid-cols-3 sm:gap-6">
        {[
          {
            title: "Flat-rate pricing",
            body: "Unlimited searches, unlimited tracking. No credits to count, no surprise bills.",
          },
          {
            title: "LinkedIn-first",
            body: "The only short-form tool that tracks LinkedIn video alongside TikTok, YouTube, and Instagram.",
          },
          {
            title: "Insight → publish loop",
            body: "Find an outlier, generate a content brief, schedule a response — all in one tool.",
          },
        ].map((feature) => (
          <div
            key={feature.title}
            className="rounded-lg border border-border bg-card p-6 text-left"
          >
            <h3 className="font-semibold">{feature.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{feature.body}</p>
          </div>
        ))}
      </div>

      {/* How it works */}
      <div className="mx-auto mt-16 max-w-4xl sm:mt-28" id="how-it-works">
        <h2 className="mb-2 text-center text-2xl font-bold sm:text-3xl">
          How it works
        </h2>
        <p className="mx-auto mb-12 max-w-xl text-center text-sm text-muted-foreground sm:text-base">
          Three steps from trend discovery to published content.
        </p>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {[
            {
              step: "1",
              icon: Search,
              title: "Search & discover",
              body: "Search any topic across YouTube, Instagram, TikTok, and LinkedIn. Our Z-score outlier detection flags the videos that are breaking out of the noise — before they peak.",
            },
            {
              step: "2",
              icon: Sparkles,
              title: "Generate a brief",
              body: "Click any outlier to generate an AI content brief: hook analysis, suggested caption, hashtags, and a call to action. Cached per video so your whole team can reference it.",
            },
            {
              step: "3",
              icon: CalendarPlus,
              title: "Schedule & publish",
              body: "Upload your response video, pick a time, and Cliplift publishes it to YouTube or Instagram on schedule. Track performance from the same dashboard.",
            },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.step} className="text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Icon className="h-6 w-6 text-primary" />
                </div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-primary">
                  Step {item.step}
                </div>
                <h3 className="text-lg font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {item.body}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Social proof */}
      <div className="mx-auto mt-16 max-w-4xl sm:mt-28">
        <h2 className="mb-10 text-center text-2xl font-bold sm:text-3xl">
          What early users say
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {[
            {
              quote:
                "We switched from Virlo after burning through credits in 3 days. Cliplift's flat rate means we actually track everything we need to.",
              name: "Sarah K.",
              role: "Content Lead, GrowthOps Agency",
            },
            {
              quote:
                "The LinkedIn analytics alone justified the switch. Nobody else tracks LinkedIn video performance — we were flying blind before Cliplift.",
              name: "Marcus T.",
              role: "B2B Video Creator, 45K followers",
            },
            {
              quote:
                "The outlier detection → AI brief → schedule flow saves me 2 hours per video. I used to do all of that manually across 3 different tools.",
              name: "Priya D.",
              role: "YouTube Shorts Creator, 120K subs",
            },
          ].map((t) => (
            <div
              key={t.name}
              className="rounded-lg border bg-card p-6"
            >
              <Quote className="mb-3 h-5 w-5 text-primary/40" />
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t.quote}
              </p>
              <div className="mt-4 border-t pt-3">
                <p className="text-sm font-semibold">{t.name}</p>
                <p className="text-xs text-muted-foreground">{t.role}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pricing */}
      <div className="container mx-auto mt-16 max-w-5xl sm:mt-28" id="pricing">
        <h2 className="mb-2 text-center text-2xl font-bold sm:text-3xl">
          Simple, flat-rate pricing
        </h2>
        <p className="mx-auto mb-8 max-w-xl text-center text-sm text-muted-foreground sm:mb-12 sm:text-base">
          No credits, no per-action charges, no surprise bills. Pick a plan that
          fits your team and track as much as you want.
        </p>
        <PricingTable />
      </div>

      {/* FAQ */}
      <div className="mx-auto mt-16 max-w-3xl sm:mt-28" id="faq">
        <h2 className="mb-10 text-center text-2xl font-bold sm:text-3xl">
          Frequently asked questions
        </h2>
        <div className="divide-y">
          {[
            {
              q: "How is Cliplift different from Virlo?",
              a: "Virlo charges credits for every action — tracking a creator costs 15 credits, tracking a video costs 10. Their Starter plan gives 2,000/mo, which agencies burn through in days. Cliplift is flat-rate: unlimited tracking, unlimited searches, no credits ever. We also cover LinkedIn video (Virlo doesn't) and include a built-in publishing pipeline.",
            },
            {
              q: "Do I need API keys to get started?",
              a: "No. Cliplift runs fully in mock mode without any API keys. You can search trends, create niches, and explore the dashboard with deterministic sample data. When you're ready for real data, just add your API keys — no code changes needed.",
            },
            {
              q: "Which platforms do you track?",
              a: "YouTube Shorts, Instagram Reels, TikTok, and LinkedIn video. We're the only short-form analytics tool that includes LinkedIn. Data comes from official APIs and trusted third-party providers (Netrows for LinkedIn, Data365 for TikTok).",
            },
            {
              q: "Can I publish directly from Cliplift?",
              a: "Yes. Connect your YouTube or Instagram account via OAuth, upload a video, set a schedule time, and Cliplift's publish worker handles the rest. You can link each post to the outlier video that inspired it for a complete insight-to-action trail.",
            },
            {
              q: "What happens when my trial ends?",
              a: "Your 7-day trial gives you full Creator-tier access. When it ends, you can pick any plan to continue. If you don't subscribe, your data stays safe — you can still view your dashboard and export, but new tracking and publishing are paused until you choose a plan.",
            },
            {
              q: "Is there an API for the Agency plan?",
              a: "API access is included with the Agency plan ($149/mo). It provides programmatic access to search, tracking, analytics, and publishing endpoints. Documentation is available at /docs on your backend instance.",
            },
          ].map((item) => (
            <details key={item.q} className="group py-4">
              <summary className="flex cursor-pointer items-center justify-between text-sm font-semibold">
                {item.q}
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </div>

      {/* Comparison CTA */}
      <div className="mx-auto mt-16 max-w-2xl text-center sm:mt-24">
        <p className="text-sm text-muted-foreground">
          Switching from another tool?{" "}
          <Link
            href="/compare/virlo"
            className="font-medium text-primary hover:underline"
          >
            See how Cliplift compares to Virlo →
          </Link>
        </p>
      </div>
    </div>
  );
}
