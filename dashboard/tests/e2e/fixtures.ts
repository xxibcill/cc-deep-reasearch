import { test as base, expect } from "@playwright/test";

type ContrastCheckOptions = {
  level?: "aa" | "aaa";
};

// Extend test with custom contrast fixture
export const test = base.extend<{
  checkPageContrast: (selector: string, options?: ContrastCheckOptions) => Promise<void>;
}>({
  checkPageContrast: async ({ page }, use) => {
    const checkContrast = async (selector: string, options: ContrastCheckOptions = {}) => {
      const level = options.level ?? "aa";
      const minimumRatio = level === "aaa" ? 7 : 4.5;

      const results = await page.evaluate(
        ({ sel, minRatio }) => {
          // Relative luminance (WCAG 2.1)
          const getLuminance = (r: number, g: number, b: number): number => {
            const normalize = (c: number) => {
              c = c / 255;
              return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
            };
            return 0.2126 * normalize(r) + 0.7152 * normalize(g) + 0.0722 * normalize(b);
          };

          const parseColor = (color: string): [number, number, number] | null => {
            const hex = color.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
            if (hex) return [parseInt(hex[1], 16), parseInt(hex[2], 16), parseInt(hex[3], 16)];

            const shortHex = color.match(/^#([0-9a-f])([0-9a-f])([0-9a-f])$/i);
            if (shortHex) {
              return [
                parseInt(shortHex[1] + shortHex[1], 16),
                parseInt(shortHex[2] + shortHex[2], 16),
                parseInt(shortHex[3] + shortHex[3], 16),
              ];
            }

            const rgb = color.match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
            if (rgb) return [parseInt(rgb[1]), parseInt(rgb[2]), parseInt(rgb[3])];

            return null;
          };

          const elements = Array.from(document.querySelectorAll(sel));
          const failures: string[] = [];

          for (const el of elements) {
            const computed = window.getComputedStyle(el);
            const text = el.textContent?.trim().substring(0, 30) || "";
            if (!text) continue;

            const fg = parseColor(computed.color);
            const bg = parseColor(computed.backgroundColor);

            if (!fg || !bg) continue;

            const l1 = getLuminance(...fg);
            const l2 = getLuminance(...bg);
            const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);

            const fontSize = parseFloat(computed.fontSize);
            const isLarge = fontSize >= 18 || (fontSize >= 14 && parseInt(computed.fontWeight) >= 700);
            const requiredRatio = isLarge ? 3 : minRatio;

            if (ratio < requiredRatio) {
              failures.push(
                `<${el.tagName.toLowerCase()}> "${text}" - ratio ${ratio.toFixed(2)}:1 (needs ${requiredRatio}:1)`
              );
            }
          }

          return failures;
        },
        { sel: selector, minRatio: minimumRatio }
      );

      if (results.length > 0) {
        throw new Error(`Contrast check failed for ${results.length} elements:\n${results.join("\n")}`);
      }
    };

    await use(checkContrast);
  },
});

export { expect };
