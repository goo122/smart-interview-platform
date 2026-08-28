import { Button } from "@/components/ui/button";
import { Image, Newspaper, SlidersHorizontal, Sparkles } from "lucide-react";

export default function HomeQuickActions() {
  return (
    <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
      <Button variant="outline" className="h-9 rounded-full text-sm">
        <Sparkles className="w-4 h-4 mr-1" />
        DeepSearch
      </Button>
      <Button variant="outline" className="h-9 rounded-full text-sm">
        <Image className="w-4 h-4 mr-1" />
        Imagine
      </Button>
      <Button variant="outline" className="h-9 rounded-full text-sm">
        <Newspaper className="w-4 h-4 mr-1" />
        新闻摘要
      </Button>
      <Button variant="outline" className="h-9 rounded-full text-sm">
        <SlidersHorizontal className="w-4 h-4 mr-1" />
        语音翻译
      </Button>
    </div>
  );
}
