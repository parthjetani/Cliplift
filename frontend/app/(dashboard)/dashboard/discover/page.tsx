import { SearchForm } from "@/components/discover/search-form";

export const metadata = {
  title: "Discover",
};

export default function DashboardDiscoverPage() {
  return (
    <div className="container max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Discover trends</h1>
        <p className="mt-2 text-muted-foreground">
          Search across all 4 platforms. Track creators or save videos directly from results.
        </p>
      </div>

      <SearchForm />
    </div>
  );
}
