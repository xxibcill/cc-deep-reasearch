import { expect, type Page } from "@playwright/test";

import { mockDashboardApis } from "./dashboard-mocks";

export type OperatorSurface = {
  name: string;
  path: string;
  readyHeading: string;
};

export const operatorSurfaces: OperatorSurface[] = [
  {
    name: "research archive",
    path: "/",
    readyHeading: "Operations overview",
  },
  {
    name: "telemetry monitor",
    path: "/session/research-report-003/monitor",
    readyHeading: "Telemetry Monitor",
  },
  {
    name: "session comparison",
    path: "/compare?a=research-report-003&b=research-deep-004",
    readyHeading: "Session Comparison",
  },
  {
    name: "analytics dashboard",
    path: "/analytics",
    readyHeading: "System health",
  },
];

export async function openOperatorSurface(page: Page, surface: OperatorSurface): Promise<void> {
  await mockDashboardApis(page);
  await page.goto(surface.path);
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: surface.readyHeading })).toBeVisible();
  await expect(page.locator("main")).toBeVisible();
}
