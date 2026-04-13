import { SearchForm } from "@/components/discover/search-form";

export const metadata = {
  title: "Discover trending short-form videos",
  description:
    "Search YouTube Shorts, Instagram Reels, LinkedIn video, and TikTok in one place. Spot outliers before they peak. No login required.",
};

export default function DiscoverPage() {
  return (
    <div className="container max-w-7xl px-4 py-6 sm:px-6 sm:py-12">
      <div className="mb-6 max-w-2xl sm:mb-8">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Discover trends</h1>
        <p className="mt-2 text-muted-foreground">
          Search across YouTube, Instagram, LinkedIn, and TikTok.
          Outliers performing 3+ standard deviations above their peers are
          flagged automatically.{" "}
          <span className="font-medium text-foreground">No login required.</span>
        </p>
      </div>

      <SearchForm />
    </div>
  );
}
