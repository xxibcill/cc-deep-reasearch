import { Page } from "@playwright/test";

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
    type ParsedColor = { rgb: RgbColor; alpha: number };

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

    function parseColor(color: string): ParsedColor | null {
      const hexMatch = color.match(/^#([0-9a-f]{6})$/i);
      if (hexMatch) {
        return {
          rgb: [
            parseInt(hexMatch[1].slice(0, 2), 16),
            parseInt(hexMatch[1].slice(2, 4), 16),
            parseInt(hexMatch[1].slice(4, 6), 16),
          ],
          alpha: 1,
        };
      }

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

    function blendColors(foreground: ParsedColor, background: ParsedColor): ParsedColor {
      const alpha = foreground.alpha + background.alpha * (1 - foreground.alpha);
      if (alpha <= 0) {
        return { rgb: [255, 255, 255], alpha: 0 };
      }

      const rgb = foreground.rgb.map((channel, index) => {
        const blended =
          (channel * foreground.alpha
            + background.rgb[index] * background.alpha * (1 - foreground.alpha))
          / alpha;
        return Math.round(blended);
      }) as RgbColor;

      return { rgb, alpha };
    }

    function resolveBackground(element: HTMLElement): ParsedColor {
      const layers: ParsedColor[] = [];
      let current: HTMLElement | null = element;
      while (current) {
        const parsed = parseColor(window.getComputedStyle(current).backgroundColor);
        if (parsed && parsed.alpha > 0) {
          layers.push(parsed);
        }
        current = current.parentElement;
      }

      const pageBackground =
        parseColor(window.getComputedStyle(document.documentElement).backgroundColor)
        ?? parseColor(window.getComputedStyle(document.body).backgroundColor)
        ?? { rgb: [255, 255, 255], alpha: 1 };

      return layers.reduceRight(
        (composite, layer) => blendColors(layer, composite),
        pageBackground
      );
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

      if (!fg) {
        return [];
      }

      const ratio = getContrastRatio(fg.rgb, background.rgb);
      const fontSize = parseFloat(computed.fontSize);
      const isLargeText = fontSize >= 18 || (fontSize >= 14 && parseInt(computed.fontWeight) >= 700);

      return [{
        element: `<${node.tagName.toLowerCase()}> "${text.substring(0, 50)}..."`,
        foreground,
        background: `rgb(${background.rgb.join(", ")})`,
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
