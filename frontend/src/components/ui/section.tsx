import { cn } from "@/lib/utils";

interface SectionProps {
  id?: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
  eyebrow?: string;
}

export function Section({
  id,
  title,
  description,
  children,
  className,
  action,
  eyebrow,
}: SectionProps) {
  return (
    <section id={id} className={cn("scroll-mt-28", className)}>
      <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? (
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-[1.75rem]">
            {title}
          </h2>
          {description ? (
            <p className="mt-2 text-sm leading-relaxed text-slate-600 sm:text-[0.95rem]">
              {description}
            </p>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
