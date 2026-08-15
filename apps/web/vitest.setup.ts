import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// @testing-library/react's auto-cleanup relies on a global `afterEach`,
// which vitest only provides when `test.globals: true` is set. We don't
// enable that (prefer explicit imports), so unmount manually instead.
afterEach(() => {
  cleanup();
});
