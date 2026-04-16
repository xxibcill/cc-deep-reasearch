/**
 * Count words in text with Thai language support.
 * Thai text (U+0E00–U+0E7F) doesn't use spaces between words,
 * so we count Thai character clusters as words.
 */
export function countWords(text: string): number {
  if (!text) return 0

  // Check if text contains Thai script
  const thaiRegex = /[\u0E00-\u0E7F]/g
  const hasThai = thaiRegex.test(text)

  if (hasThai) {
    // For Thai: count clusters of Thai characters separated by non-Thai
    // Each continuous run of Thai characters counts as one word
    const thaiWords = text.match(/[\u0E00-\u0E7F]+/g)
    if (thaiWords && thaiWords.length > 0) {
      // Count Thai word clusters
      let thaiWordCount = thaiWords.length

      // For mixed Thai/Latin text, also count the non-Thai words
      const nonThaiParts = text.split(/[\u0E00-\u0E7F]+/).filter(Boolean)
      for (const part of nonThaiParts) {
        // Each non-Thai segment - count space-separated words
        thaiWordCount += part.split(/\s+/).filter(Boolean).length
      }

      return thaiWordCount
    }
  }

  // Default: split on whitespace
  return text.split(/\s+/).filter(Boolean).length
}
