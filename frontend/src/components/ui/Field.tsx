import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const inputClass =
  "h-11 w-full rounded-chip border border-mist bg-paper px-3 text-sm text-ink placeholder:text-pewter transition-colors hover:border-steel focus:border-lime-dark focus:outline-none focus:ring-2 focus:ring-lime/50";

function Wrap({ id, label, hint, children, className }: { id: string; label: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] font-medium text-graphite">
        {label}
      </label>
      {children}
      {hint && <span className="text-[11px] text-pewter">{hint}</span>}
    </div>
  );
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: ReactNode;
  wrapClassName?: string;
}

export function TextField({ label, hint, wrapClassName, className, id, ...props }: TextFieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Wrap id={fid} label={label} hint={hint} className={wrapClassName}>
      <input id={fid} className={cn(inputClass, className)} {...props} />
    </Wrap>
  );
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: ReactNode;
  options: { value: string; label: string }[];
  wrapClassName?: string;
}

export function SelectField({ label, hint, options, wrapClassName, className, id, ...props }: SelectFieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Wrap id={fid} label={label} hint={hint} className={wrapClassName}>
      <select id={fid} className={cn(inputClass, "cursor-pointer pr-8", className)} {...props}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Wrap>
  );
}

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: ReactNode;
  wrapClassName?: string;
}

export function TextAreaField({ label, hint, wrapClassName, className, id, ...props }: TextAreaFieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <Wrap id={fid} label={label} hint={hint} className={wrapClassName}>
      <textarea id={fid} className={cn(inputClass, "h-auto min-h-24 py-2.5", className)} {...props} />
    </Wrap>
  );
}
