"""Text normalization utilities for cleaning scraped content.

This module provides comprehensive text cleaning to remove navigation elements,
UI artifacts, and other noise from web-scraped content before analysis.
"""

import re
from typing import Any
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode


# Navigation and commerce terms to filter out
NAVIGATION_TERMS = frozenset({
    "home", "cart", "submit manuscript", "newsletter", "follow us",
    "shop", "blog", "about", "contact", "rewards", "register",
    "login", "menu", "search", "merchandise", "who we are",
    "best sellers", "new", "free shipping", "checkout", "sign up",
    "subscribe", "join our email", "continue shopping", "estimated total",
    "related products", "you may also like", "customer reviews",
})

# Content indicators that suggest real content vs UI
CONTENT_INDICATORS = frozenset({
    "health", "benefit", "study", "research", "tea", "antioxidant",
    "cell", "damage", "cancer", "heart", "skin", "weight", "diabetes",
    "inflammation", "immune", "bone", "dental", "brain", "liver",
    "metabolism", "polyphenol", "catechin", "flavonoid", "extract",
    "clinical", "effect", "result", "show", "found", "suggest",
    "contain", "include", "help", "reduce", "prevent", "improve",
    "according", "reported", "published", "journal", "scientist",
    "evidence", "find", "data", "analysis", "trial", "review",
})

# Navigation header patterns
NAV_HEADER_PATTERNS = frozenset({
    r"^#{1,3}\s*Shop\s*$",
    r"^#{1,3}\s*Blog\s*$",
    r"^#{1,3}\s*About\s*(Us)?\s*$",
    r"^#{1,3}\s*Contact\s*$",
    r"^#{1,3}\s*Cart\s*$",
    r"^#{1,3}\s*Menu\s*$",
    r"^#{1,3}\s*Best\s+Sellers?\s*$",
    r"^#{1,3}\s*Who\s+We\s+Are\s*$",
    r"^#{1,3}\s*What\s+is\s+Matcha?\s*$",
    r"^#{1,3}\s*Find\s+Relief\s*$",
    r"^#{1,3}\s*Steeping\s+Accessories\s*$",
    r"^#{1,3}\s*Your\s+cart\s*$",
    r"^#{1,3}\s*Estimated\s+total\s*$",
    r"^#{1,3}\s*Continue\s+shopping\s*$",
    r"^#{1,3}\s*Origins\s+of\s*$",
    r"^#{1,3}\s*Related\s+products?\s*$",
    r"^#{1,3}\s*You\s+may\s+also\s+like\s*$",
    r"^#{1,3}\s*Customer\s+reviews?\s*$",
    r"^#{1,3}\s*Newsletter\s*$",
    r"^#{1,3}\s*Follow\s+us\s*$",
})

# UI line patterns
UI_LINE_PATTERNS = frozenset({
    r"^SHOP\s*$",
    r"^BLOG\s*$",
    r"^ABOUT\s*$",
    r"^CONTACT\s*$",
    r"^REWARDS\s*$",
    r"^REGISTER\s*$",
    r"^LOGIN\s*$",
    r"^CART\s*$",
    r"^MENU\s*$",
    r"^SEARCH\s*$",
    r"^HOME\s*$",
    r"^ALL\s+TEAS?\s*$",
    r"^GREEN\s+TEA\s*$",
    r"^BLACK\s+TEA\s*$",
    r"^WHITE\s+TEA\s*$",
    r"^OOLONG\s+TEA\s*$",
    r"^MERCHANDISE\s*$",
    r"^WHO\s+WE\s+ARE\s*$",
    r"^WHY\s+GREEN\s+TEA\??\s*$",
    r"^BEST\s+SELLERS?\s*$",
    r"^NEW\s*!\s*$",
    r"^FREE\s+.*SHIPPING\s*$",
})

# Common website artifacts
ARTIFACT_PATTERNS = frozenset({
    r"Share\s+this\s*:",
    r"Follow\s+us\s*:",
    r"Skip\s+to\s+content",
    r"Continue\s+shopping",
    r"Have\s+an\s+account",
    r"Check\s+out\s+faster",
    r"Estimated\s+total",
    r"Your\s+cart\s+is\s+empty",
    r"Best\s+Sellers?",
    r"Shop\s+our\s+best\s+selling",
    r"Find\s+Relief\s+Now",
    r"Free\s+US\s+Shipping",
    r"Shipping\s+on\s+orders",
    r"Sign\s+up\s+for\s+our\s+newsletter",
    r"Subscribe\s+to\s+our\s+newsletter",
    r"Join\s+our\s+email\s+list",
    r"Get\s+\d+%\s+off",
    r"Use\s+code\s*:",
    r"com/@\w+",
    r"\(\d+\)",
    r"\*\s*\+\s*",
    r"######\s*",
    r"\[\]\([^\)]*\)",
})

# Navigation buttons and links
NAV_LINK_PATTERNS = frozenset({
    r"\[Log in\]",
    r"\[Cart\]",
    r"\[Sign up\]",
    r"\[Menu\]",
    r"\[Close\]",
    r"\[Share\]",
    r"\[Register\]",
    r"\(Log in\)",
    r"\(Cart\)",
    r"\(Sign up\)",
    r"\[Skip to content\]",
    r"\[Continue shopping\]",
    r"\[Have an account",
    r"\[Login\]",
    r"\[Sign Up\]",
    r"\*?\s*Twitter",
    r"\*?\s*Facebook",
    r"\*?\s*Instagram",
    r"\*?\s*YouTube",
    r"\*?\s*Pinterest",
    r"\*?\s*LinkedIn",
    r"Follow us on",
    r"Subscribe to",
    r"Join our",
})


def normalize_content(content: str, is_title: bool = False) -> str:
    """Normalize scraped content by removing navigation, UI artifacts, and noise.

    Args:
        content: Raw content to normalize.
        is_title: Whether this is a title (applies shorter cleaning).

    Returns:
        Cleaned content suitable for analysis.
    """
    if not content:
        return ""

    # Remove blob URLs and internal references
    content = re.sub(r"blob:http://[^\s]+", "", content)
    content = re.sub(r"\[Image\s*\d+\]", "", content)
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content)

    # Remove markdown links but keep text (for content)
    content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)

    # Remove navigation buttons and social media
    for pattern in NAV_LINK_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # Remove lines that are purely UI elements
    for pattern in UI_LINE_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.MULTILINE)

    # Remove markdown headers that are navigation
    for pattern in NAV_HEADER_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE | re.MULTILINE)

    # Remove common website artifacts
    for pattern in ARTIFACT_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # Remove email addresses and URLs from content
    content = re.sub(r"\S+@\S+\.\S+", "", content)
    content = re.sub(r"https?://\S+", "", content)

    # Clean up markdown link artifacts - remove lines that are just links
    content = re.sub(r"^\s*\[[^\]]*\]\s*$", "", content, flags=re.MULTILINE)

    # Remove lines with excessive special characters (UI artifacts)
    content = re.sub(r"^[^a-zA-Z0-9]*$", "", content, flags=re.MULTILINE)

    # Clean up extra whitespace
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)

    # For titles, just trim and return
    if is_title:
        return content.strip()[:200]

    # Process line by line for better filtering
    return _normalize_content_lines(content)


def _normalize_content_lines(content: str) -> str:
    """Normalize content by filtering lines and preserving sentence boundaries.

    Args:
        content: Pre-cleaned content.

    Returns:
        Line-filtered content.
    """
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip very short lines (likely UI)
        if len(line) < 15:
            continue

        # Skip lines that are just numbers or special chars
        if re.match(r"^[\d\s\*\-\+\#\[\]\(\)]+$", line):
            continue

        # Skip lines dominated by navigation terms
        if _is_navigation_line(line):
            continue

        # Skip lines that are mostly markdown artifacts
        if line.count("#") > 3 or line.count("*") > 3:
            continue

        # Keep lines with content indicators or reasonable word count
        if _has_content_indicators(line) or _has_reasonable_word_count(line):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _is_navigation_line(line: str) -> bool:
    """Check if a line is dominated by navigation terms.

    Args:
        line: Line to check.

    Returns:
        True if line appears to be navigation.
    """
    line_lower = line.lower()

    # Check if line is mostly title case navigation tokens
    words = line.split()
    title_case_count = sum(1 for w in words if w and w[0].isupper())
    all_caps_count = sum(1 for w in words if w.isupper())

    if len(words) > 0 and (title_case_count / len(words) > 0.5 or all_caps_count / len(words) > 0.3):
        # Check if words are navigation terms
        nav_word_count = sum(1 for w in words if w.lower() in NAVIGATION_TERMS)
        if nav_word_count / len(words) > 0.3:
            return True

    # Check if line contains mostly commerce/UI terms
    nav_token_count = sum(1 for token in NAVIGATION_TERMS if token in line_lower)
    if nav_token_count >= 2 or (nav_token_count > 0 and len(line) < 50):
        return True

    return False


def _has_content_indicators(line: str) -> bool:
    """Check if line contains words suggesting real content.

    Args:
        line: Line to check.

    Returns:
        True if line contains content indicators.
    """
    line_lower = line.lower()
    return any(indicator in line_lower for indicator in CONTENT_INDICATORS)


def _has_reasonable_word_count(line: str) -> bool:
    """Check if line has a reasonable number of meaningful words.

    Args:
        line: Line to check.

    Returns:
        True if line has 3+ words of length 3+.
    """
    words = [w for w in line.split() if len(w) > 2]
    return len(words) >= 3


def extract_full_sentence_around_keyword(
    text: str,
    keyword: str,
    context_sentences: int = 1,
) -> str:
    """Extract the full sentence(s) containing a keyword with optional context.

    This replaces fragment extraction with sentence-window extraction to ensure
    complete sentences in safety and contradiction sections.

    Args:
        text: Full text to search in.
        keyword: Keyword to find.
        context_sentences: Number of adjacent sentences to include.

    Returns:
        Complete sentence(s) containing the keyword, or empty string if not found.
    """
    if not keyword or not text:
        return ""

    # Find keyword position (case-insensitive)
    keyword_lower = keyword.lower()
    text_lower = text.lower()
    pos = text_lower.find(keyword_lower)

    if pos == -1:
        return ""

    # Find sentence boundaries around the keyword
    text_length = len(text)

    # Find start of sentence
    start_pos = pos
    while start_pos > 0 and text[start_pos - 1] not in ".!?":
        start_pos -= 1

    # Find end of sentence
    end_pos = pos + len(keyword)
    while end_pos < text_length and text[end_pos] not in ".!?":
        end_pos += 1
    end_pos = min(end_pos + 1, text_length)  # Include the period

    # Extract base sentence
    base_sentence = text[start_pos:end_pos].strip()

    # Add context sentences if requested
    if context_sentences > 0:
        # Look backward for context
        context_start = start_pos
        sentences_found = 0
        while context_start > 0 and sentences_found < context_sentences:
            context_start -= 1
            if text[context_start] in ".!?":
                sentences_found += 1
        if sentences_found < context_sentences:
            context_start = 0

        # Look forward for context
        context_end = end_pos
        sentences_found = 0
        while context_end < text_length and sentences_found < context_sentences:
            if text[context_end] in ".!?":
                sentences_found += 1
            context_end += 1

        return text[context_start:context_end].strip()

    return base_sentence


def is_complete_sentence(text: str) -> bool:
    """Check if text is a complete sentence, not a fragment.

    Args:
        text: Text to validate.

    Returns:
        True if text appears to be a complete sentence.
    """
    if not text or len(text) < 10:
        return False

    text = text.strip()

    # Must end with sentence terminator
    if not text.endswith((".", "!", "?")):
        return False

    # Must not start with lowercase without preceding context
    if text[0].islower():
        return False

    # Must not end mid-word
    if text.rstrip(".!?").endswith(("...", "…", "ing", "tion", "ment")):
        # These could be valid, so check more carefully
        pass

    # Must have at least one verb (simple heuristic)
    verbs = {"is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
             "do", "does", "did", "will", "would", "could", "should", "may",
             "might", "must", "can", "need", "suggest", "show", "find", "report",
             "indicate", "demonstrate", "reveal", "support", "conclude", "state"}
    words = set(text.lower().split())
    has_verb = any(verb in words for verb in verbs)

    if not has_verb:
        return False

    # Must not start with conjunction-only fragments
    first_word = text.split()[0].lower() if text.split() else ""
    if first_word in {"with", "and", "or", "but", "for", "nor", "so", "yet"}:
        return False

    # Must have reasonable length for a complete thought
    if len(text.split()) < 4:
        return False

    return True




__all__ = [
    "normalize_content",
    "extract_full_sentence_around_keyword",
    "is_complete_sentence",
    "sanitize_url",
]
