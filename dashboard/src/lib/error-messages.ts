const ERROR_MESSAGES: Record<string, { title: string; guidance: string }> = {
  network: {
    title: 'Connection failed',
    guidance: 'Check that the research backend is running and accessible.',
  },
  404: {
    title: 'Not found',
    guidance: 'This resource may have been deleted. Return to the list and refresh.',
  },
  401: {
    title: 'Unauthorized',
    guidance: 'Your API key may be invalid or expired. Check Settings.',
  },
  429: {
    title: 'Rate limited',
    guidance: 'Too many requests. Wait a moment and try again.',
  },
  500: {
    title: 'Server error',
    guidance: 'The backend encountered an error. Check the server logs for details.',
  },
  websocket: {
    title: 'Live updates paused',
    guidance: 'The dashboard will reconnect automatically when the connection is restored.',
  },
};

export function getErrorGuidance(error: string): { title: string; guidance: string } {
  const lower = error.toLowerCase();

  if (lower.includes('network') || lower.includes('fetch') || lower.includes('econnrefused')) {
    return ERROR_MESSAGES.network;
  }
  if (lower.includes('404') || lower.includes('not found')) {
    return ERROR_MESSAGES['404'];
  }
  if (lower.includes('401') || lower.includes('unauthorized') || lower.includes('api key')) {
    return ERROR_MESSAGES['401'];
  }
  if (lower.includes('429') || lower.includes('rate limit') || lower.includes('too many')) {
    return ERROR_MESSAGES['429'];
  }
  if (lower.includes('500') || lower.includes('internal server')) {
    return ERROR_MESSAGES['500'];
  }
  if (lower.includes('websocket') || lower.includes('ws:') || lower.includes('socket')) {
    return ERROR_MESSAGES.websocket;
  }

  return { title: 'Something went wrong', guidance: '' };
}
