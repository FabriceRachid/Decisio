// Tiny global toast system — dispatch events that <Toaster/> picks up.
export type ToastVariant = "success" | "info" | "warning" | "error";

export type ToastDetail = {
  id: number;
  message: string;
  description?: string;
  variant: ToastVariant;
};

let counter = 0;

export function toast(
  message: string,
  opts: { description?: string; variant?: ToastVariant } = {}
) {
  if (typeof window === "undefined") return;
  const detail: ToastDetail = {
    id: ++counter,
    message,
    description: opts.description,
    variant: opts.variant ?? "info",
  };
  window.dispatchEvent(new CustomEvent<ToastDetail>("decisio:toast", { detail }));
}
