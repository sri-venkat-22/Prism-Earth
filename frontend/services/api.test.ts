import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, getFields, getHealth, getPresets, postAsk, postFetch } from "@/services/api";

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}): Response {
  const { ok = true, status = 200 } = init;
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  } as unknown as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("successful requests", () => {
  it("GET returns the parsed body and hits the right path", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ presets: [] }));
    const body = await getPresets();
    expect(body).toEqual({ presets: [] });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/meta/presets");
  });

  it("builds the query string for field filters", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ fields: [] }));
    await getFields({ layer: "terrain", available: true });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("layer=terrain");
    expect(url).toContain("available=true");
  });

  it("POST sends a JSON body and returns the response", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ answer: "ok", citations: [] }));
    const res = await postAsk({ lat: 17.4, lng: 78.5, question: "why?" });
    expect(res).toMatchObject({ answer: "ok" });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({ question: "why?" });
  });
});

describe("error handling", () => {
  it("parses the SRS §28.2 error envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: "RATE_LIMIT_EXCEEDED",
            message: "Rate limit exceeded.",
            correlation_id: "REQ-1",
          },
        },
        { ok: false, status: 429 },
      ),
    );
    await expect(getHealth()).rejects.toMatchObject({
      status: 429,
      code: "RATE_LIMIT_EXCEEDED",
      correlationId: "REQ-1",
    });
  });

  it("parses a FastAPI validation-error array", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: [{ msg: "must be >= -90", loc: ["body", "lat"] }] },
        { ok: false, status: 422 },
      ),
    );
    const err = await postFetch({ lat: -999, lng: 0, preset: "terrain" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("VALIDATION_ERROR");
    expect(err.message).toContain("body.lat");
  });

  it("parses a FastAPI string detail", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Not found" }, { ok: false, status: 404 }),
    );
    await expect(getHealth()).rejects.toMatchObject({ status: 404, message: "Not found" });
  });

  it("falls back to status text when the error body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);
    await expect(getHealth()).rejects.toMatchObject({ status: 500 });
  });

  it("wraps network-level failures as a NETWORK_ERROR", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(getHealth()).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });
});
