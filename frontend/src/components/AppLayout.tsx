import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/context";

const navItems = [
  { to: "/", label: "首页", end: true },
  { to: "/chat", label: "AI 对话" },
  { to: "/interview", label: "模拟面试" },
  { to: "/interview/reports", label: "面试报告" },
];

export function AppLayout() {
  const { status, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate("/auth", { replace: true });
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="寻知首页">
          <span className="brand-mark">寻</span>
          <span>
            <strong>寻知</strong>
            <small>智能模拟面试</small>
          </span>
        </NavLink>
        <nav className="main-nav" aria-label="主导航">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-actions">
          {status === "AUTHENTICATED" ? (
            <>
              <span className="user-chip" title={user?.email}>
                <span className="avatar">{user?.username.slice(0, 1).toUpperCase()}</span>
                {user?.username}
              </span>
              <button className="button button-quiet" type="button" onClick={handleLogout}>
                退出
              </button>
            </>
          ) : (
            <NavLink className="button button-primary" to="/auth">
              登录 / 注册
            </NavLink>
          )}
        </div>
      </header>
      <main className="page-content">
        <Outlet />
      </main>
    </div>
  );
}
