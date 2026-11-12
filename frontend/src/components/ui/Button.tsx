import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { buttonClass, type ButtonSize, type ButtonVariant } from "./buttonClass";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "secondary", size = "md", type = "button", ...props },
  ref,
) {
  return <button ref={ref} type={type} className={buttonClass(variant, size, className)} {...props} />;
});

interface ButtonLinkProps extends LinkProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function ButtonLink({ className, variant = "secondary", size = "md", ...props }: ButtonLinkProps) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}
