import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a successful request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "1", name: "Test" }]), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const projects = await api.listProjects();

    expect(projects).toEqual([{ id: "1", name: "Test" }]);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/projects"),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("throws an ApiError with the server's detail message on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Project not found" }), { status: 404 }),
      ),
    );

    await expect(api.getProject("missing-id")).rejects.toMatchObject({
      name: "ApiError",
      message: "Project not found",
      status: 404,
    });
  });

  it("throws an ApiError when the network request itself fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(api.listProjects()).rejects.toBeInstanceOf(ApiError);
  });
});
