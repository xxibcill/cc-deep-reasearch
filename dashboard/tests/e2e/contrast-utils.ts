import { Page, Locator } from "@playwright/test";

interface ContrastResult {
  element: string;
  foreground: string;
  background: string;
  ratio: number;
  passes: {
    aa: boolean;
    aaLarge: boolean;
    aaa: boolean;
    aaaLarge: boolean;
  };
}

// Relative luminance calculation (WCAG 2.1)
function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

// Calculate contrast ratio between two colors
function getContrastRatio(fg: [number, number, number], bg: [number, number, number]): number {
  const l1 = getLuminance(...fg);
  const l2 = getLuminance(...bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// Parse CSS color to RGB
function parseColor(color: string): [number, number, number] | null {
  // Handle hex
  const hexMatch = color.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (hexMatch) {
    return [parseInt(hexMatch[1], 16), parseInt(hexMatch[2], 16), parseInt(hexMatch[3], 16)];
  }
  // Handle shorthand hex
  const shortHexMatch = color.match(/^#([0-9a-f])([0-9a-f])([0-9a-f])$/i);
  if (shortHexMatch) {
    return [
      parseInt(shortHexMatch[1] + shortHexMatch[1], 16),
      parseInt(shortHexMatch[2] + shortHexMatch[2], 16),
      parseInt(shortHexMatch[3] + shortHexMatch[3], 16),
    ];
  }
  // Handle rgb/rgba
  const rgbMatch = color.match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (rgbMatch) {
    return [parseInt(rgbMatch[1]), parseInt(rgbMatch[2]), parseInt(rgbMatch[3])];
  }
  return null;
}

export async function checkContrast(
  page: Page,
  selector: string,
  options: { minimumRatio?: number } = {}
): Promise<ContrastResult[]> {
  const results: ContrastResult[] = [];
  const minimumRatio = options.minimumRatio ?? 4.5; // WCAG AA default

  const elements = await page.locator(selector).all();

  for (const element of elements) {
    const styles = await element.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
        fontSize: computed.fontSize,
        fontWeight: computed.fontWeight,
        tagName: el.tagName,
        text: el.textContent?.trim().substring(0, 50) || "",
      };
    });

    const fg = parseColor(styles.color);
    const bg = parseColor(styles.backgroundColor);

    if (!fg || !bg) continue;

    const ratio = getContrastRatio(fg, bg);
    const fontSize = parseFloat(styles.fontSize);
    const isLargeText = fontSize >= 18 || (fontSize >= 14 && parseInt(styles.fontWeight) >= 700);

    results.push({
      element: `<${styles.tagName.toLowerCase()}> "${styles.text}..."`,
      foreground: styles.color,
      background: styles.backgroundColor,
      ratio: Math.round(ratio * 100) / 100,
      passes: {
        aa: isLargeText ? ratio >= 3 : ratio >= 4.5,
        aaLarge: ratio >= 3,
        aaa: isLargeText ? ratio >= 4.5 : ratio >= 7,
        aaaLarge: ratio >= 4.5,
      },
    });
  }

  return results;
}

export function expectContrastToPass(results: ContrastResult[], level: "aa" | "aaa" = "aa"): void {
  const failures = results.filter((r) => !r.passes[level]);

  if (failures.length > 0) {
    const messages = failures.map(
      (f) => `${f.element}\n  Ratio: ${f.ratio}:1 (needed ${level === "aa" ? "4.5" : "7"}:1)\n  FG: ${f.foreground}\n  BG: ${f.background}`
    );
    throw new Error(`Contrast check failed for ${failures.length} elements:\n\n${messages.join("\n\n")}`);
  }
}
