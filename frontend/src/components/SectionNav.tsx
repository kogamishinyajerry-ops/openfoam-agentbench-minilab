import { useEffect, useState } from "react";

export interface NavSection {
  id: string;
  label: string;
}

/**
 * Subtle right-side dot navigation for the long presentation dashboard.
 * Tracks the section in view (IntersectionObserver) and smooth-scrolls on click.
 * Hidden below lg — on a laptop/projector it lets a presenter jump anywhere.
 */
export default function SectionNav({ sections }: { sections: NavSection[] }) {
  const [active, setActive] = useState<string>(sections[0]?.id ?? "");

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-40% 0px -55% 0px", threshold: [0, 0.5, 1] }
    );
    sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [sections]);

  const jump = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <nav
      aria-label="章节导航"
      className="fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 lg:block"
    >
      <ul className="space-y-1.5">
        {sections.map((s) => {
          const on = active === s.id;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={on ? "true" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  jump(s.id);
                }}
                className="group flex items-center justify-end gap-2"
              >
                <span
                  className={`whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium transition-all duration-200 ${
                    on
                      ? "bg-white/10 text-cyan-200 opacity-100"
                      : "text-slate-400 opacity-0 group-hover:opacity-100"
                  }`}
                >
                  {s.label}
                </span>
                <span
                  className={`h-2 w-2 shrink-0 rounded-full transition-all duration-200 ${
                    on
                      ? "scale-125 bg-cyan-400 shadow-glow"
                      : "bg-white/25 group-hover:bg-white/60"
                  }`}
                />
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
