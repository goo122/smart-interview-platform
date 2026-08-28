import { APP_BRAND_NAME } from "@/lib/branding";

type ChatPageHeaderProps = {
  selectedModelName?: string;
};

export default function ChatPageHeader({
  selectedModelName,
}: ChatPageHeaderProps) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white/50 px-6 py-4 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <img
          src="/xunzhi-mark.svg"
          alt={APP_BRAND_NAME}
          className="h-8 w-8 rounded-full border border-slate-200 object-cover"
        />
        <h2 className="font-semibold">{APP_BRAND_NAME}</h2>
        {selectedModelName ? (
          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-600">
            {selectedModelName}
          </span>
        ) : null}
      </div>
    </div>
  );
}
