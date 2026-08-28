import { Button } from "@/components/ui/button";

export default function HomeTopBar() {
  return (
    <div className="flex items-center justify-end text-sm text-slate-500 gap-3">
      <Button variant="ghost" className="h-8 px-3 rounded-full text-slate-500">
        私密模式
      </Button>
      <Button variant="ghost" className="h-8 px-3 rounded-full text-slate-500">
        分享
      </Button>
    </div>
  );
}
