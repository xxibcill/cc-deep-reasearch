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

export async function checkContrast(
  page: Page,
  selector: string,
  options: { minimumRatio?: number } = {}
): Promise<ContrastResult[]> {
  return page.locator(selector).evaluateAll((elements) => {
    type RgbColor = [number, number, number];

    function getLuminance(r: number, g: number, b: number): number {
      const [rs, gs, bs] = [r, g, b].map((c) => {
        c = c / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
    }

    function getContrastRatio(fg: RgbColor, bg: RgbColor): number {
      const l1 = getLuminance(...fg);
      const l2 = getLuminance(...bg);
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    }

    function parseColor(color: string): { rgb: RgbColor; alpha: number } | null {
      const rgbMatch = color.match(
        /rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)/
      );
      if (rgbMatch) {
        return {
          rgb: [parseInt(rgbMatch[1]), parseInt(rgbMatch[2]), parseInt(rgbMatch[3])],
          alpha: rgbMatch[4] ? parseFloat(rgbMatch[4]) : 1,
        };
      }
      return null;
    }

    function resolveBackground(element: HTMLElement): string {
      let current: HTMLElement | null = element;
      while (current) {
        const backgroundColor = window.getComputedStyle(current).backgroundColor;
        const parsed = parseColor(backgroundColor);
        if (parsed && parsed.alpha > 0) {
          return backgroundColor;
        }
        current = current.parentElement;
      }
      return window.getComputedStyle(document.body).backgroundColor;
    }

    function getVisibleText(element: HTMLElement): string {
      if (element instanceof HTMLInputElement) {
        const type = element.type.toLowerCase();
        if (
          [
            "checkbox",
            "radio",
            "button",
            "submit",
            "reset",
            "range",
            "file",
            "hidden",
            "color",
            "image",
          ].includes(type)
        ) {
          return "";
        }
        return (element.value || element.placeholder || element.getAttribute("aria-label") || "").trim();
      }

      if (element instanceof HTMLTextAreaElement) {
        return (element.value || element.placeholder || element.getAttribute("aria-label") || "").trim();
      }

      if (element instanceof HTMLSelectElement) {
        return (
          element.selectedOptions[0]?.textContent ||
          element.getAttribute("aria-label") ||
          ""
        ).trim();
      }

      return (element.textContent || "").trim();
    }

    return elements.flatMap((node) => {
      if (!(node instanceof HTMLElement)) {
        return [];
      }

      const computed = window.getComputedStyle(node);
      if (computed.display === "none" || computed.visibility === "hidden") {
        return [];
      }

      const text = getVisibleText(node);
      if (!text) {
        return [];
      }

      const foreground = computed.color;
      const background = resolveBackground(node);
      const fg = parseColor(foreground);
      const bg = parseColor(background);

      if (!fg || !bg) {
        return [];
      }

      const ratio = getContrastRatio(fg.rgb, bg.rgb);
      const fontSize = parseFloat(computed.fontSize);
      const isLargeText = fontSize >= 18 || (fontSize >= 14 && parseInt(computed.fontWeight) >= 700);

      return [{
        element: `<${node.tagName.toLowerCase()}> "${text.substring(0, 50)}..."`,
        foreground,
        background,
        ratio: Math.round(ratio * 100) / 100,
        passes: {
          aa: isLargeText ? ratio >= 3 : ratio >= 4.5,
          aaLarge: ratio >= 3,
          aaa: isLargeText ? ratio >= 4.5 : ratio >= 7,
          aaaLarge: ratio >= 4.5,
        },
      }];
    });
  });
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
