import { describe, expect, it } from "vitest";

import { DEV_TOOLS } from "@/lib/dev";

describe("DEV_TOOLS", () => {
  it("is a boolean derived from NEXT_PUBLIC_DEV_TOOLS", () => {
    expect(typeof DEV_TOOLS).toBe("boolean");
  });
});
