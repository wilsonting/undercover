import type { Status } from "./api";
import { STATUS_LABELS } from "./format";

export function StatusLabel({ status }: Readonly<{ status: Status }>) {
  return <span className={`status ${status}`}>{STATUS_LABELS[status]}</span>;
}
