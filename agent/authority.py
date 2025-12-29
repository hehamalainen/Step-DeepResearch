"""Authority ranking for source evaluation."""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class AuthorityScore:
    """Authority score for a source."""
    tier: str  # official, academic, industry, media, other
    score: float  # 0-1 score
    reason: str


# Curated lists of authoritative domains
OFFICIAL_DOMAINS = {
    # Government
    ".gov", ".gov.uk", ".gov.au", ".gov.ca", ".europa.eu", ".gc.ca",
    "whitehouse.gov", "congress.gov", "sec.gov", "fda.gov", "cdc.gov",
    "nist.gov", "nih.gov", "nsf.gov", "state.gov", "justice.gov",
    
    # International organizations
    "un.org", "who.int", "worldbank.org", "imf.org", "oecd.org",
    "wto.org", "nato.int", "iso.org", "itu.int",
}

ACADEMIC_DOMAINS = {
    # Top universities
    ".edu", ".ac.uk", ".edu.au", ".edu.cn",
    "harvard.edu", "stanford.edu", "mit.edu", "berkeley.edu",
    "oxford.ac.uk", "cambridge.ac.uk", "ethz.ch", "epfl.ch",
    
    # Academic publishers and archives
    "nature.com", "science.org", "sciencedirect.com", "springer.com",
    "wiley.com", "ieee.org", "acm.org", "arxiv.org", "ssrn.com",
    "pubmed.gov", "ncbi.nlm.nih.gov", "scholar.google.com",
    "plos.org", "frontiersin.org", "mdpi.com",
}

INDUSTRY_DOMAINS = {
    # Tech companies (research/docs)
    "research.google", "ai.google", "research.facebook.com", "research.microsoft.com",
    "openai.com", "anthropic.com", "deepmind.com", "huggingface.co",
    "aws.amazon.com", "cloud.google.com", "azure.microsoft.com",
    "developer.apple.com", "developer.android.com",
    
    # Industry standards bodies
    "w3.org", "ietf.org", "oasis-open.org", "openapis.org",
    "github.com", "stackoverflow.com", "devdocs.io",
    
    # Major consulting/research firms
    "mckinsey.com", "bcg.com", "bain.com", "gartner.com",
    "forrester.com", "idc.com", "statista.com",
}

MEDIA_DOMAINS = {
    # Major news outlets
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "wsj.com", "ft.com", "economist.com", "bloomberg.com",
    
    # Tech media
    "techcrunch.com", "wired.com", "arstechnica.com",
    "theverge.com", "zdnet.com", "cnet.com",
}

# Patterns that indicate low-quality content
LOW_QUALITY_PATTERNS = [
    r"^(www\.)?pinterest\.",
    r"^(www\.)?facebook\.com",
    r"^(www\.)?twitter\.com",
    r"^(www\.)?instagram\.com",
    r"^(www\.)?tiktok\.com",
    r"quora\.com/",
    r"reddit\.com/r/",
    r"medium\.com/@",
    r"blogspot\.com",
    r"wordpress\.com",
    r"tumblr\.com",
    r"affiliate",
    r"sponsored",
]


def evaluate_source_authority(url: str) -> AuthorityScore:
    """
    Evaluate the authority of a source based on its URL.
    
    Args:
        url: The URL to evaluate
        
    Returns:
        AuthorityScore with tier, score, and reason
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        full_url = url.lower()
        
        # Remove www prefix
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Check for low-quality patterns first
        for pattern in LOW_QUALITY_PATTERNS:
            if re.search(pattern, full_url, re.IGNORECASE):
                return AuthorityScore(
                    tier="other",
                    score=0.2,
                    reason=f"Matches low-quality pattern: {pattern}"
                )
        
        # Check official domains
        for official in OFFICIAL_DOMAINS:
            if domain.endswith(official) or domain == official.lstrip("."):
                return AuthorityScore(
                    tier="official",
                    score=1.0,
                    reason=f"Official/government domain: {domain}"
                )
        
        # Check academic domains
        for academic in ACADEMIC_DOMAINS:
            if domain.endswith(academic) or domain == academic.lstrip("."):
                return AuthorityScore(
                    tier="academic",
                    score=0.95,
                    reason=f"Academic/research domain: {domain}"
                )
        
        # Check industry domains
        for industry in INDUSTRY_DOMAINS:
            if industry in domain:
                return AuthorityScore(
                    tier="industry",
                    score=0.85,
                    reason=f"Industry/standards domain: {domain}"
                )
        
        # Check media domains
        for media in MEDIA_DOMAINS:
            if media in domain:
                return AuthorityScore(
                    tier="media",
                    score=0.75,
                    reason=f"Established media domain: {domain}"
                )
        
        # Check for common TLDs that might indicate quality
        if domain.endswith(".org"):
            return AuthorityScore(
                tier="other",
                score=0.6,
                reason="Organization domain (.org)"
            )
        
        if domain.endswith(".io") or domain.endswith(".dev"):
            return AuthorityScore(
                tier="other",
                score=0.5,
                reason="Tech-focused domain"
            )
        
        # Default for unknown sources
        return AuthorityScore(
            tier="other",
            score=0.4,
            reason=f"Unknown domain authority: {domain}"
        )
        
    except Exception as e:
        logger.error(f"Error evaluating source authority: {e}")
        return AuthorityScore(
            tier="other",
            score=0.3,
            reason=f"Error parsing URL: {str(e)}"
        )


def rank_sources(
    sources: list[dict],
    prefer_authority: bool = True,
) -> list[dict]:
    """
    Rank sources by authority and relevance.
    
    Args:
        sources: List of source dicts with 'url' field
        prefer_authority: Whether to boost authoritative sources
        
    Returns:
        Sorted list of sources with authority scores added
    """
    scored_sources = []
    
    for source in sources:
        url = source.get("url", "")
        authority = evaluate_source_authority(url)
        
        scored_source = {
            **source,
            "authority_tier": authority.tier,
            "authority_score": authority.score,
            "authority_reason": authority.reason,
        }
        
        scored_sources.append(scored_source)
    
    if prefer_authority:
        # Sort by authority score (descending)
        scored_sources.sort(key=lambda x: x["authority_score"], reverse=True)
    
    return scored_sources


def filter_low_quality(
    sources: list[dict],
    min_score: float = 0.3,
) -> list[dict]:
    """
    Filter out low-quality sources.
    
    Args:
        sources: List of source dicts with authority scores
        min_score: Minimum authority score to keep
        
    Returns:
        Filtered list of sources
    """
    return [s for s in sources if s.get("authority_score", 0) >= min_score]


def get_authority_summary(sources: list[dict]) -> dict:
    """
    Get a summary of authority distribution across sources.
    
    Args:
        sources: List of source dicts with authority tiers
        
    Returns:
        Dict with counts and percentages by tier
    """
    tiers = {"official": 0, "academic": 0, "industry": 0, "media": 0, "other": 0}
    
    for source in sources:
        tier = source.get("authority_tier", "other")
        tiers[tier] = tiers.get(tier, 0) + 1
    
    total = len(sources)
    
    return {
        "counts": tiers,
        "percentages": {
            tier: (count / total * 100) if total > 0 else 0
            for tier, count in tiers.items()
        },
        "total": total,
    }
