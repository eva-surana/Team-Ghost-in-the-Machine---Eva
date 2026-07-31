import { Github, Star } from "lucide-react";

/**
 * GithubButton — drop this into your header/nav, top-right.
 * Copy just this component into your project; swap `href` and `stars`
 * for your real repo (or wire `stars` up to the GitHub API if you want
 * a live count).
 */
export function GithubButton({
  href = "https://github.com/eva-surana/Team-Ghost-in-the-Machine---Eva",
  label = "GitHub",
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group inline-flex items-center rounded-full border border-slate-200 bg-white/90 backdrop-blur-sm shadow-sm transition-all duration-200 hover:border-slate-300 hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2"
    >
      <span className="flex items-center gap-2 pl-3 sm:pl-4 pr-3 py-2 text-sm font-semibold text-slate-800">
        <Github className="h-4 w-4 text-slate-700 transition-transform duration-200 group-hover:-rotate-6" />
        <span className="hidden sm:inline">{label}</span>
      </span>
    </a>
  );
}

export default function Navbar() {
  return (
    <div className="absolute top-0 left-0 w-full z-50">
      <header className="w-full flex items-center justify-between px-6 py-5 bg-white/50 backdrop-blur-md border-b border-white/20">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-slate-900 flex items-center justify-center">
            <span className="text-white text-xs font-bold">A</span>
          </div>
          <span className="text-slate-900 font-bold text-lg tracking-tight">
            Aletheon
          </span>
        </div>

        <GithubButton />
      </header>
    </div>
  );
}
