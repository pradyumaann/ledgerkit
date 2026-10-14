import { X } from "@phosphor-icons/react";
import { type ReactNode, useEffect, useRef } from "react";

/** A modal built on the native dialog element, which supplies focus trapping and Escape. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        // A click on the backdrop lands on the dialog element itself.
        if (event.target === ref.current) onClose();
      }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-[20px] bg-surface p-0 text-ink shadow-float ring-1 ring-line backdrop:bg-[rgb(23_23_33/0.45)] open:animate-rise"
    >
      {open && (
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[17px]">{title}</h2>
              {description && <p className="mt-1 text-ink-2">{description}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="-m-1.5 rounded-full p-1.5 text-ink-3 transition-colors hover:bg-wash hover:text-ink"
            >
              <X size={18} />
            </button>
          </div>
          <div className="mt-5">{children}</div>
        </div>
      )}
    </dialog>
  );
}
