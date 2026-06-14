import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount React trees between tests so the jsdom document doesn't leak state
// across cases (the suite doesn't enable vitest globals, so register it here).
afterEach(() => {
  cleanup();
});
