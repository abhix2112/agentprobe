import { Link, NavLink, Outlet } from "react-router-dom";
import { ShieldHalf } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export default function App() {
  return (
    <div className="min-h-full">
      <header className="app-glow sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-5">
          <Link to="/" className="flex items-center gap-2">
            <ShieldHalf className="h-5 w-5 text-primary" />
            <span className="text-sm font-semibold tracking-tight">agentprobe</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavItem to="/" label="Dashboard" end />
            <NavItem to="/new" label="New run" />
          </nav>
          <div className="ml-auto">
            <Link to="/new">
              <Button size="sm">New run</Button>
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded-md px-2.5 py-1.5 transition-colors",
          isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
        )
      }
    >
      {label}
    </NavLink>
  );
}
