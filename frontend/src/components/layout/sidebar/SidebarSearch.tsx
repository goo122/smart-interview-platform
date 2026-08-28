import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

type SidebarSearchProps = {
  isCollapsed?: boolean;
};

export default function SidebarSearch({ isCollapsed }: SidebarSearchProps) {
  if (isCollapsed) return null;

  return (
    <div className="px-4 pb-4">
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <Input
          placeholder="搜索"
          className="pl-9 h-9 rounded-full bg-slate-50 border-slate-100"
        />
      </div>
    </div>
  );
}