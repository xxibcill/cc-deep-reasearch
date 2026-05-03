import { contentGenClient, getContentGenErrorMessage } from './client';
import type { PublishItem } from '@/types/content-gen';

export async function listPublishQueue(): Promise<PublishItem[]> {
  try {
    const response = await contentGenClient.get('/publish');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list publish queue.'));
  }
}

export async function removeFromQueue(
  ideaId: string,
  platform: string,
): Promise<void> {
  try {
    await contentGenClient.delete(`/publish/${ideaId}/${platform}`);
  } catch (error) {
    throw new Error(
      getContentGenErrorMessage(error, 'Failed to remove item from publish queue.'),
    );
  }
}