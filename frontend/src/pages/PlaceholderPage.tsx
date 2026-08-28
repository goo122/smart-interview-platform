import { Link } from "react-router-dom";

export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <section className="placeholder-page">
      <p className="eyebrow">COMING NEXT</p>
      <h1>{title}</h1>
      <p>{description}</p>
      <Link className="button button-primary" to="/">
        回到首页
      </Link>
    </section>
  );
}
