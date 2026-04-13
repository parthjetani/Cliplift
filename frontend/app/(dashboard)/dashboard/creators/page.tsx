import { PageHeader } from "@/components/shared/page-header";
import { CreatorList } from "@/components/creators/creator-list";

export const metadata = {
  title: "Tracked Creators",
};

export default function CreatorsPage() {
  return (
    <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Tracked Creators"
        description="Creators you're following. We snapshot their metrics daily and flag outlier videos."
      />
      <CreatorList />
    </div>
  );
}
