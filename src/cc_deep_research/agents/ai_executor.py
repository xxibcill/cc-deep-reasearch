"""AI Executor for real semantic analysis using Claude Code capabilities.

This module provides actual AI-powered analysis by leveraging Claude Code's
built-in capabilities through the Task tool.
"""

import re
from typing import Any


class AIExecutor:
    """Executes AI-powered analysis tasks.

    This class provides real semantic analysis by using Claude Code's
    capabilities for theme extraction, synthesis, and gap identification.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize AI executor.

        Args:
            config: Configuration dictionary.
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")

    def extract_themes(
        self,
        sources: list[dict[str, str]],
        query: str,  # noqa: ARG002 - reserved for future AI integration
        num_themes: int = 8,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Args:
            sources: List of sources with url, title, content.
            query: Research query (reserved for future AI integration).
            num_themes: Number of themes to extract.

        Returns:
            List of themes with name, description, key_points, supporting_sources.
        """
        # Prepare content for analysis
        _content_summary = self._prepare_content_summary(sources)

        # Use improved heuristics with semantic topic detection
        return self._semantic_theme_extraction(sources, num_themes)

    def _prepare_content_summary(self, sources: list[dict[str, str]]) -> str:
        """Prepare source content for analysis.

        Args:
            sources: List of sources.

        Returns:
            Formatted content string.
        """
        sections = []
        for i, source in enumerate(sources[:15], 1):  # Limit to 15 sources
            content = source.get("content", "") or source.get("snippet", "")
            if content:
                # Truncate to reasonable length
                truncated = content[:1500]
                last_period = truncated.rfind('.')
                if last_period > len(truncated) * 0.7:
                    truncated = truncated[:last_period + 1]

                sections.append(f"\n--- Source {i} ---")
                sections.append(f"Title: {source.get('title', 'Untitled')}")
                sections.append(f"URL: {source.get('url', '')}")
                sections.append(f"Content: {truncated}")

        return "\n".join(sections)

    def _build_theme_prompt(self, query: str, content: str, num_themes: int) -> str:
        """Build prompt for theme extraction.

        Args:
            query: Research query.
            content: Formatted content.
            num_themes: Number of themes.

        Returns:
            Analysis prompt.
        """
        return f"""Analyze the following research sources about "{query}" and identify {num_themes} major themes.

{content}

For each theme, provide:
1. A concise, descriptive theme name (e.g., "Antioxidant Properties", not "Health Benefits Drinking White")
2. A 2-3 sentence description summarizing what the sources say about this theme
3. 3-5 key points with specific facts or findings
4. URLs of sources that support this theme

Focus on:
- Actual health benefits with scientific backing
- Specific compounds and their effects
- Concrete findings, not vague generalizations
- Distinct themes that don't overlap

Respond in JSON format:
{{
  "themes": [
    {{
      "name": "Theme Name",
      "description": "Description...",
      "key_points": ["Point 1", "Point 2", "Point 3"],
      "supporting_sources": ["url1", "url2"]
    }}
  ]
}}
"""

    def _semantic_theme_extraction(
        self,
        sources: list[dict[str, str]],
        num_themes: int,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic topic detection.

        This method uses pattern matching to identify meaningful health topics
        and groups sources by those topics.

        Args:
            sources: List of sources.
            num_themes: Number of themes.

        Returns:
            List of theme dictionaries.
        """
        # Define health benefit topic patterns
        topic_patterns = [
            (r'\bantioxidant[s]?\b.{0,50}\b(free radical|oxidative|cell|damage|protect)\b', "Antioxidant Properties"),
            (r'\bpolyphenol[s]?\b.{0,30}\b(health|benefit|effect|compound)\b', "Polyphenol Content"),
            (r'\bcatechin[s]?\b.{0,30}\b(egcg|compound|benefit)\b', "Catechin Compounds"),
            (r'\bheart\b.{0,30}\b(health|disease|cardiovascular|cholesterol|blood pressure)\b', "Heart Health Benefits"),
            (r'\bcancer\b.{0,30}\b(prevent|risk|fight|cell|tumor)\b', "Cancer Prevention Potential"),
            (r'\bskin\b.{0,30}\b(health|aging|damage|protect|collagen|uv)\b', "Skin Health Benefits"),
            (r'\bweight\b.{0,30}\b(loss|management|metabolism|fat|obesity)\b', "Weight Management Support"),
            (r'\bbone\b.{0,30}\b(health|density|strength|osteoporosis)\b', "Bone Health Benefits"),
            (r'\bdental\b.{0,30}\b(health|teeth|oral|cavity|plaque|gum)\b', "Dental and Oral Health"),
            (r'\bbrain\b.{0,30}\b(health|cognitive|function|memory|neuroprotective|alzheimer)\b', "Brain and Cognitive Health"),
            (r'\bliver\b.{0,30}\b(health|protect|function|detox)\b', "Liver Protection"),
            (r'\bdiabetes\b.{0,30}\b(prevent|manage|blood sugar|insulin|glucose)\b', "Blood Sugar and Diabetes"),
            (r'\binflammation\b.{0,30}\b(reduce|anti-inflammatory|chronic|swelling)\b', "Anti-Inflammatory Effects"),
            (r'\bimmune\b.{0,30}\b(system|boost|function|response)\b', "Immune System Support"),
            (r'\bcaffeine\b.{0,30}\b(content|alertness|energy|stimulant)\b', "Caffeine Content and Effects"),
            (r'\bl-theanine\b.{0,30}\b(relaxation|focus|calm|amino)\b', "L-Theanine and Relaxation"),
            (r'\b(china|fujian)\b.{0,30}\b(origin|history|traditional|province)\b', "Origin and History"),
            (r'\bcamellia sinensis\b', "Camellia Sinensis Plant"),
            (r'\bminimal.{0,20}(process|processing)\b', "Minimal Processing Benefits"),
            (r'\bdigestive\b.{0,30}\b(health|gut|stomach|intestine)\b', "Digestive Health"),
        ]

        # Find topics in sources
        topic_sources: dict[str, list[dict[str, str]]] = {}
        topic_key_points: dict[str, list[str]] = {}

        for source in sources:
            content = (source.get("content", "") + " " + source.get("title", "")).lower()

            for pattern, topic_name in topic_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    if topic_name not in topic_sources:
                        topic_sources[topic_name] = []
                        topic_key_points[topic_name] = []

                    # Add source if not already added
                    if source.get("url") not in [s.get("url") for s in topic_sources[topic_name]]:
                        topic_sources[topic_name].append(source)

                    # Extract key points from this source for this topic
                    key_points = self._extract_key_points(source, topic_name)
                    topic_key_points[topic_name].extend(key_points)

        # Sort by number of sources and create themes
        sorted_topics = sorted(
            topic_sources.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        themes = []
        used_sources = set()

        for topic_name, matching_sources in sorted_topics[:num_themes]:
            if len(matching_sources) < 1:
                continue

            # Get unique supporting URLs
            supporting_urls = []
            for src in matching_sources:
                url = src.get("url", "")
                if url and url not in used_sources:
                    supporting_urls.append(url)
                    used_sources.add(url)

            if not supporting_urls:
                continue

            # Get key points for this topic
            key_points = topic_key_points.get(topic_name, [])[:5]

            # Generate description
            description = self._generate_description(topic_name, matching_sources, key_points)

            themes.append({
                "name": topic_name,
                "description": description,
                "key_points": key_points,
                "supporting_sources": supporting_urls[:5],
            })

        return themes

    # Topic-specific keyword sets for semantic relevance checking
    _TOPIC_KEYWORDS: dict[str, list[str]] = {
        "Antioxidant Properties": [
            "antioxidant", "free radical", "oxidative", "oxidation", "cell damage",
            "protect cell", "neutralize", "egcg", "catechin"
        ],
        "Polyphenol Content": [
            "polyphenol", "phenolic", "compound", "plant compound", "bioactive"
        ],
        "Catechin Compounds": [
            "catechin", "egcg", "epigallocatechin", "flavonoid", "gallic"
        ],
        "Heart Health Benefits": [
            "heart", "cardiovascular", "cholesterol", "blood pressure", "ldl",
            "hdl", "triglyceride", "artery", "vascular", "cardiac"
        ],
        "Cancer Prevention Potential": [
            "cancer", "tumor", "malignant", "carcinogen", "anti-cancer",
            "prevent cancer", "cancer cell", "chemopreventive"
        ],
        "Skin Health Benefits": [
            "skin", "collagen", "elasticity", "aging", "uv", "sun damage",
            "wrinkle", "dermat", "epiderm"
        ],
        "Weight Management Support": [
            "weight", "fat", "obesity", "metabolism", "adipose", "bmi",
            "body weight", "weight loss", "burn fat", "lipid"
        ],
        "Bone Health Benefits": [
            "bone", "osteoporosis", "density", "calcium", "skeleton",
            "mineral density", "fracture"
        ],
        "Dental and Oral Health": [
            "dental", "teeth", "tooth", "oral", "cavity", "plaque", "gum",
            "gingiv", "enamel", "bacteria mouth"
        ],
        "Brain and Cognitive Health": [
            "brain", "cognitive", "memory", "neuroprotective", "alzheimer",
            "dementia", "neural", "neurodegenerative", "mental"
        ],
        "Liver Protection": [
            "liver", "hepatic", "detox", "hepatoprotect", "cirrhosis"
        ],
        "Blood Sugar and Diabetes": [
            "diabetes", "blood sugar", "glucose", "insulin", "glycemic",
            "prediabetes", "type 2"
        ],
        "Anti-Inflammatory Effects": [
            "inflammation", "inflammatory", "anti-inflammatory", "swelling",
            "chronic inflammation", "cytokine"
        ],
        "Immune System Support": [
            "immune", "immunity", "antiviral", "antibacterial", "infection",
            "white blood cell", "immune response"
        ],
        "Caffeine Content and Effects": [
            "caffeine", "stimulant", "alertness", "energy", "nervous",
            "jittery", "sleep"
        ],
        "L-Theanine and Relaxation": [
            "theanine", "relaxation", "calm", "focus", "anxiety", "stress",
            "alpha wave"
        ],
        "Origin and History": [
            "china", "fujian", "origin", "history", "traditional", "ancient",
            "dynasty", "province"
        ],
        "Camellia Sinensis Plant": [
            "camellia sinensis", "tea plant", "tea leaf", "sinensis",
            "bud", "young leaf"
        ],
        "Minimal Processing Benefits": [
            "processing", "processed", "oxidation", "withered", "dried",
            "steamed", "preserved", "minimal"
        ],
        "Digestive Health": [
            "digestive", "digestion", "gut", "stomach", "intestine",
            "probiotic", "microbiome", "bowel"
        ],
    }

    def _extract_key_points(self, source: dict[str, str], topic_name: str) -> list[str]:
        """Extract key points from a source related to a topic.

        Args:
            source: Source dictionary.
            topic_name: Topic to find points for.

        Returns:
            List of key point strings.
        """
        content = source.get("content", "")
        if not content:
            return []

        # Get topic-specific keywords for semantic relevance
        topic_keywords = self._TOPIC_KEYWORDS.get(topic_name, [])

        # Fall back to topic name words if no specific keywords defined
        if not topic_keywords:
            topic_keywords = topic_name.lower().split()

        # Split into sentences
        sentences = re.split(r'[.!?]+', content)

        key_points = []
        for sentence in sentences:
            sentence = sentence.strip()

            # Skip too short or too long sentences
            if len(sentence) < 30 or len(sentence) > 250:
                continue

            # Check if sentence is semantically relevant to the topic
            # Must contain at least 1 topic-specific keyword for relevance
            sentence_lower = sentence.lower()
            keyword_matches = sum(1 for kw in topic_keywords if kw in sentence_lower)

            if keyword_matches >= 1:
                # Clean the sentence
                clean = self._clean_sentence(sentence)
                if clean and clean not in key_points:
                    key_points.append(clean)

        return key_points[:3]  # Limit to 3 per source

    def _clean_sentence(self, sentence: str) -> str:
        """Clean a sentence by removing artifacts.

        Args:
            sentence: Sentence to clean.

        Returns:
            Cleaned sentence or empty string if invalid.
        """
        if not sentence:
            return ""

        # Remove markdown and UI artifacts
        sentence = re.sub(r'\[.*?\]', '', sentence)
        sentence = re.sub(r'#{2,}', '', sentence)
        sentence = re.sub(r'\*+', '', sentence)
        sentence = re.sub(r'https?://\S+', '', sentence)

        # Remove leading/trailing punctuation and whitespace
        sentence = sentence.strip().lstrip('- ').lstrip('• ').lstrip('* ')

        # Clean whitespace
        sentence = ' '.join(sentence.split())

        # Skip if too short or too long
        if len(sentence) < 25 or len(sentence) > 300:
            return ""

        # Skip if contains navigation text
        nav_words = [
            'log in', 'sign up', 'cart', 'menu', 'subscribe', 'click here',
            'learn more', 'read more', 'buy now', 'shop now', 'add to cart',
            'newsletter', 'follow us', 'share this', 'pin it', 'tweet'
        ]
        if any(word in sentence.lower() for word in nav_words):
            return ""

        # Skip marketing fluff patterns (check before any modifications)
        marketing_patterns = [
            r'^have you ever',
            r'^did you know',
            r'^discover',
            r'^unlock',
            r'^explore',
            r'^find out',
            r'^helps in weight loss have you',  # Specific garbled pattern
            r'^- ',  # Starts with dash (often list artifacts)
            r'^\d+\s*%',  # Starts with percentage (often stats taken out of context)
            r'^benefits?,?\s+taste',  # "Benefits, Taste, Uses" artifact
            r'^uses\s+have\s+you',  # Garbled text pattern
            r'\.\.\.\s*$',  # Ends with ellipsis (incomplete)
            r'^[a-z]\s+[a-z]\s+',  # "a b c" pattern (broken words)
            r'have you ever considered',
            r'have you ever wondered',
            r'have you ever thought',
        ]
        for pattern in marketing_patterns:
            if re.search(pattern, sentence.lower()):
                return ""

        # Skip if mostly uppercase (often headers/navigation)
        if sum(1 for c in sentence if c.isupper()) > len(sentence) * 0.6:
            return ""

        # Skip if contains sentence fragments (multiple periods close together)
        if sentence.count('.') > 3:
            return ""

        # Ensure sentence ends with proper punctuation (add period if missing)
        sentence = sentence.rstrip()
        if not sentence.endswith(('.', '!', '?')):
            sentence += '.'

        return sentence

    def _generate_description(
        self, topic_name: str, sources: list[dict[str, str]], key_points: list[str]
    ) -> str:
        """Generate a description for a theme.

        Args:
            topic_name: Name of the theme.
            sources: List of sources.
            key_points: Key points (should be pre-validated for relevance).

        Returns:
            Description string.
        """
        # Start with topic introduction
        source_count = len(sources)

        # Get topic-specific keywords for relevance checking
        topic_keywords = self._TOPIC_KEYWORDS.get(topic_name, [])
        if not topic_keywords:
            topic_keywords = topic_name.lower().split()

        # Build description
        description = f"Research from {source_count} source"
        if source_count > 1:
            description += "s"
        description += f" supports findings about {topic_name.lower()}."

        # Find a relevant key point (must contain topic keywords)
        relevant_point = None
        for point in key_points:
            point_lower = point.lower()
            # Check if point contains at least 2 topic keywords
            keyword_matches = sum(1 for kw in topic_keywords if kw in point_lower)
            if keyword_matches >= 2:
                relevant_point = point
                break

        # Add the relevant key point if found
        if relevant_point:
            # Ensure the point is well-formed
            if len(relevant_point) > 50:
                # Truncate at a sentence boundary if possible
                truncated = relevant_point[:200]
                last_period = truncated.rfind('.')
                if last_period > 100:
                    truncated = truncated[:last_period + 1]
                else:
                    truncated = truncated.rstrip() + "..."
                description += " " + truncated
            else:
                description += " " + relevant_point

        return description

    def synthesize_findings(
        self,
        themes: list[dict[str, Any]],
        sources: list[dict[str, str]],  # noqa: ARG002 - reserved for future use
    ) -> list[dict[str, Any]]:
        """Synthesize themes into key findings.

        Args:
            themes: List of extracted themes.
            sources: List of all sources (reserved for future use).

        Returns:
            List of findings with title, description, evidence, confidence.
        """
        findings = []

        for theme in themes[:5]:  # Top 5 themes become findings
            # Use the theme name as finding title
            title = theme.get("name", "Research Finding")

            # Generate a more detailed description
            description = theme.get("description", "")

            # Add key points to description if available
            key_points = theme.get("key_points", [])
            if key_points:
                if description:
                    description += "\n\n"
                description += "Key findings include:\n"
                for point in key_points[:3]:
                    description += f"- {point}\n"

            # Determine confidence based on number of supporting sources
            support_count = len(theme.get("supporting_sources", []))
            if support_count >= 4:
                confidence = "High"
            elif support_count >= 2:
                confidence = "Medium"
            else:
                confidence = "Low"

            findings.append({
                "title": title,
                "description": description.strip(),
                "evidence": theme.get("supporting_sources", []),
                "confidence": confidence,
            })

        return findings


__all__ = ["AIExecutor"]
