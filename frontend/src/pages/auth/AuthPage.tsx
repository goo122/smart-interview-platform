import AuthMarketingPanel from "@/components/auth/AuthMarketingPanel";
import AuthFormCard from "@/components/auth/AuthFormCard";
import { useAuthPageController } from "@/hooks/auth/useAuthPageController";

export default function AuthPage() {
  const {
    mode,
    formData,
    loading,
    error,
    registerLoading,
    localError,
    switchMode,
    handleInputChange,
    handleSubmit,
  } = useAuthPageController();

  return (
    <div className="h-full w-full bg-white relative overflow-hidden flex items-center justify-center px-6 py-10">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-24 -left-16 h-80 w-80 rounded-full bg-indigo-300/25 blur-2xl motion-reduce:animate-none animate-[pulse_8s_ease-in-out_infinite]" />
        <div className="absolute -bottom-20 right-[-60px] h-[360px] w-[360px] rounded-full bg-cyan-300/20 blur-2xl motion-reduce:animate-none animate-[pulse_9s_ease-in-out_infinite]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(15,23,42,0.10),transparent_60%),radial-gradient(circle_at_bottom,rgba(14,116,144,0.12),transparent_55%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(148,163,184,0.06),rgba(14,116,144,0.06),rgba(99,102,241,0.06))]" />
      </div>

      <div className="relative w-full max-w-5xl grid gap-10 lg:grid-cols-[1.1fr_0.9fr] items-center">
        <AuthMarketingPanel />
        <AuthFormCard
          mode={mode}
          formData={formData}
          errorMessage={error || localError}
          isSubmitting={loading || registerLoading}
          onSwitchMode={switchMode}
          onInputChange={handleInputChange}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}
