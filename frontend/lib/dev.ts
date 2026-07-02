// Dev-only surface gate (SRS §12 nav rules). Explore and System are developer
// tools: they are appended to navigation ONLY when this flag is set, so they are
// omitted from the rendered DOM entirely for normal users (not merely hidden with
// CSS). The pages themselves stay reachable by direct route.
//
// Enable locally with NEXT_PUBLIC_DEV_TOOLS=true in .env.local.
export const DEV_TOOLS = process.env.NEXT_PUBLIC_DEV_TOOLS === "true";
