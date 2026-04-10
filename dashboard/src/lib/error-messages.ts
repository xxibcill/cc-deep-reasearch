interface ErrorGuidance {
  guidance: string | null;
}

export function getErrorGuidance(_error: string): ErrorGuidance {
  return { guidance: null };
}
