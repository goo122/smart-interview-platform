import { Link } from "react-router-dom";
import { useAuth } from "@/features/auth/context";

const highlights = [
  ["01", "资料有序沉淀", "把准备过程和每一次练习都留在自己的空间里。"],
  ["02", "AI 陪练反馈", "用结构化反馈找到下一次回答可以更好的地方。"],
  ["03", "从容面对面试", "从首页开始，逐步建立清晰、可信的表达节奏。"],
];

export function HomePage() {
  const { status, user } = useAuth();
  const destination = status === "AUTHENTICATED" ? "/interview" : "/auth";

  return (
    <section className="home-page">
      <div className="hero-glow hero-glow-one" />
      <div className="hero-glow hero-glow-two" />
      <div className="hero-copy">
        <p className="eyebrow">XUNZHI · AI INTERVIEW STUDIO</p>
        <h1>
          让每一次准备，<em>更有方向。</em>
        </h1>
        <p className="hero-description">
          {user ? `欢迎回来，${user.username}。` : "从一次轻松的练习开始，"}
          我们把面试准备变成一段可持续、可复盘的成长旅程。
        </p>
        <div className="hero-actions">
          <Link className="button button-primary button-large" to={destination}>
            {status === "AUTHENTICATED" ? "开始练习" : "立即开始"}
            <span aria-hidden="true">→</span>
          </Link>
          <Link className="text-link" to="/auth">
            已有账号？登录
          </Link>
        </div>
      </div>
      <div className="hero-card" aria-label="产品概览">
        <div className="hero-card-top">
          <span className="status-dot" />
          <span>准备状态</span>
          <span className="hero-card-status">随时开始</span>
        </div>
        <div className="hero-card-score">∞</div>
        <p>清晰的思路，来自持续的练习。</p>
        <div className="hero-card-bars">
          <span style={{ width: "82%" }} />
          <span style={{ width: "64%" }} />
          <span style={{ width: "74%" }} />
        </div>
      </div>
      <div className="highlight-grid">
        {highlights.map(([number, title, body]) => (
          <article key={number} className="highlight-card">
            <span className="highlight-number">{number}</span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
