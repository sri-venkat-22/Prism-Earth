import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A pill badge. The visual variant is applied via className using the token
 * classes defined in globals.css (e.g. `badge-confidence-high`, `layer-chip`).
 */
const Badge = React.forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement>>(
  ({ className, ...props }, ref) => (
    <span ref={ref} className={cn("pe-badge badge-muted", className)} {...props} />
  ),
);
Badge.displayName = "Badge";

export { Badge };
