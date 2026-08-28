import HomeTopBar from "@/components/home/HomeTopBar";
import HomeHero from "@/components/home/HomeHero";
import HomeComposerPanel from "@/components/home/HomeComposerPanel";
import { useHomePageController } from "@/hooks/home/useHomePageController";

export default function HomePage() {
  const {
    query,
    setQuery,
    models,
    selectedModel,
    handleSend,
    handleSelectModel,
  } = useHomePageController();

  return (
    <div className="h-full w-full bg-white relative">
      <div className="absolute right-6 top-4 z-10">
        <HomeTopBar />
      </div>
      <div className="absolute inset-0 flex items-center justify-center px-4">
        <div className="flex flex-col items-center justify-center gap-7 scale-[1.1] md:scale-[1.16] origin-center w-full max-w-2xl">
          <div className="w-full space-y-7">
            <HomeHero />
            <HomeComposerPanel
              query={query}
              onQueryChange={setQuery}
              onSend={handleSend}
              models={models}
              selectedModel={selectedModel}
              onSelectModel={handleSelectModel}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
