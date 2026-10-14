import type { ReactNode } from "react";
import { cx, Skeleton } from "./primitives";

export type Column<Row> = {
  id: string;
  header: string;
  align?: "left" | "right";
  /** Columns of figures: right-aligned with tabular digits. */
  numeric?: boolean;
  className?: string;
  cell: (row: Row) => ReactNode;
};

type TableProps<Row> = {
  columns: Column<Row>[];
  rows: Row[] | undefined;
  rowKey: (row: Row) => string | number;
  onRowClick?: (row: Row) => void;
  /** Accessible name for the row action, e.g. "Open invoice INV-00012". */
  rowLabel?: (row: Row) => string;
  loading?: boolean;
  /** While refetching, the previous rows stay visible, dimmed. */
  stale?: boolean;
  footer?: ReactNode;
};

export function Table<Row>({ columns, rows, rowKey, onRowClick, rowLabel, loading, stale, footer }: TableProps<Row>) {
  return (
    <div className="overflow-x-auto">
      <table className={cx("w-full border-collapse transition-opacity duration-300", stale && "opacity-60")}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                scope="col"
                className={cx(
                  "whitespace-nowrap px-5 pb-2.5 pt-4 text-[12.5px] font-normal text-ink-3",
                  column.numeric || column.align === "right" ? "text-right" : "text-left",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading &&
            Array.from({ length: 6 }, (_, index) => (
              <tr key={index} className="border-t border-line">
                {columns.map((column) => (
                  <td key={column.id} className="px-5 py-3.5">
                    <Skeleton className={cx("h-4", column.numeric ? "ml-auto w-16" : "w-24")} />
                  </td>
                ))}
              </tr>
            ))}
          {!loading &&
            rows?.map((row) => (
              <tr
                key={rowKey(row)}
                tabIndex={onRowClick ? 0 : undefined}
                aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                className={cx(
                  "border-t border-line",
                  onRowClick && "cursor-pointer transition-colors duration-200 hover:bg-tint focus-visible:bg-tint",
                )}
              >
                {columns.map((column) => (
                  <td
                    key={column.id}
                    className={cx(
                      "px-5 py-3 align-middle",
                      column.numeric && "figures whitespace-nowrap text-right",
                      column.align === "right" && "text-right",
                      column.className,
                    )}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
        {footer && <tfoot>{footer}</tfoot>}
      </table>
    </div>
  );
}
