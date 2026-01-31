"""
Multi-source news verification using trusted news sites.
Uses NewsAPI to search for coverage across reputable sources.
"""

import os
import re
import logging
from urllib.parse import quote_plus
import requests

logger = logging.getLogger(__name__)

# Minimum number of trusted sources required for verification
MIN_TRUSTED_SOURCES = 4

# Trusted news domains (used with NewsAPI domains parameter)
# These are internationally recognized, fact-checked news organizations
TRUSTED_NEWS_DOMAINS = [
    'reuters.com',      # Reuters - international
    'apnews.com',       # Associated Press - international
    'bbc.com',          # BBC - UK
    'bbc.co.uk',
    'nytimes.com',      # New York Times - US
    'theguardian.com',  # The Guardian - UK
    'washingtonpost.com',
    'npr.org',          # NPR - US
    'aljazeera.com',    # Al Jazeera - international
    'dw.com',           # Deutsche Welle - Germany
    'france24.com',     # France 24
    'economist.com',
    'cnn.com',
    'abcnews.go.com',
    'cbsnews.com',
    'nbcnews.com',
    'thehindu.com',     # India
    'indiatoday.in',
    'indianexpress.com',
]

# Display names for domains (user-friendly)
DOMAIN_DISPLAY_NAMES = {
    'reuters.com': 'Reuters',
    'apnews.com': 'Associated Press',
    'bbc.com': 'BBC',
    'bbc.co.uk': 'BBC',
    'nytimes.com': 'The New York Times',
    'theguardian.com': 'The Guardian',
    'washingtonpost.com': 'The Washington Post',
    'npr.org': 'NPR',
    'aljazeera.com': 'Al Jazeera',
    'dw.com': 'Deutsche Welle',
    'france24.com': 'France 24',
    'economist.com': 'The Economist',
    'cnn.com': 'CNN',
    'abcnews.go.com': 'ABC News',
    'cbsnews.com': 'CBS News',
    'nbcnews.com': 'NBC News',
    'thehindu.com': 'The Hindu',
    'indiatoday.in': 'India Today',
    'indianexpress.com': 'The Indian Express',
}


def _get_domain_from_url(url):
    """Extract domain from URL for display name lookup."""
    if not url:
        return None
    match = re.search(r'https?://(?:www\.)?([^/:]+)', url)
    if match:
        domain = match.group(1).lower()
        # Normalize: reuters.com, www.reuters.com -> reuters.com
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    return None


def _is_trusted_domain(domain):
    """Check if domain is in our trusted list (handles subdomains)."""
    if not domain:
        return False
    for trusted in TRUSTED_NEWS_DOMAINS:
        if domain == trusted or domain.endswith('.' + trusted):
            return True
    return False


def _get_display_name(article):
    """Get display name for article source."""
    source = article.get('source', {}) or {}
    name = source.get('name', '')
    if name:
        return name
    url = article.get('url', '')
    domain = _get_domain_from_url(url)
    return DOMAIN_DISPLAY_NAMES.get(domain, domain or 'Unknown Source')


def _extract_search_query(text, max_length=80):
    """Extract a search query from the news text (headline or key phrases)."""
    if not text or len(text.strip()) < 10:
        return None
    # Take first sentence or first max_length chars
    text = text.strip()
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Truncate at sentence or word boundary
    if len(text) > max_length:
        cut = text[:max_length].rfind(' ')
        text = text[:cut] if cut > 40 else text[:max_length]
    return text.strip() if len(text) >= 10 else None


class NewsVerifier:
    """
    Verifies news by searching trusted sources.
    Requires NEWSAPI_KEY environment variable (free at newsapi.org).
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('NEWSAPI_KEY', '')
        self.base_url = 'https://newsapi.org/v2/everything'
        self.enabled = bool(self.api_key)

    def verify(self, text, min_sources=MIN_TRUSTED_SOURCES):
        """
        Search trusted news sources for coverage of the given text.
        Returns dict with:
          - sources: list of {name, url, title, domain}
          - unique_source_count: number of different trusted sources
          - verdict: 'Real' | 'Partially Correct' | 'Fake' based on coverage
          - trust_boost: score adjustment based on verification
          - explanation: human-readable explanation
          - success: bool
        """
        if not self.enabled:
            return {
                'success': False,
                'sources': [],
                'unique_source_count': 0,
                'verdict': None,
                'trust_boost': 0,
                'explanation': 'News verification unavailable. Set NEWSAPI_KEY in environment to enable.',
            }

        query = _extract_search_query(text)
        if not query:
            return {
                'success': False,
                'sources': [],
                'unique_source_count': 0,
                'verdict': None,
                'trust_boost': 0,
                'explanation': 'Could not extract searchable query from input.',
            }

        domains_str = ','.join(TRUSTED_NEWS_DOMAINS[:20])  # NewsAPI limit
        params = {
            'q': query,
            'domains': domains_str,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 50,
            'apiKey': self.api_key,
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=15)
            data = resp.json()

            if resp.status_code != 200:
                err_msg = data.get('message', resp.text)
                logger.warning(f"NewsAPI error: {err_msg}")
                return {
                    'success': False,
                    'sources': [],
                    'unique_source_count': 0,
                    'verdict': None,
                    'trust_boost': 0,
                    'explanation': f'News verification service error: {err_msg}',
                }

            if data.get('status') != 'ok':
                return {
                    'success': False,
                    'sources': [],
                    'unique_source_count': 0,
                    'verdict': None,
                    'trust_boost': 0,
                    'explanation': data.get('message', 'News API returned an error.'),
                }

            articles = data.get('articles', []) or []
            seen_domains = set()
            sources = []

            for art in articles:
                url = art.get('url')
                domain = _get_domain_from_url(url)
                if not domain or not _is_trusted_domain(domain):
                    continue
                # Use base domain for deduping (reuters.com not www.reuters.com)
                base = domain.split('.')[-2] + '.' + domain.split('.')[-1] if domain.count('.') >= 1 else domain
                if base in seen_domains:
                    continue
                seen_domains.add(base)
                sources.append({
                    'name': _get_display_name(art),
                    'url': url,
                    'title': art.get('title', '')[:120],
                    'domain': domain,
                })
                if len(sources) >= 10:  # Limit displayed sources
                    break

            unique_count = len(sources)

            # Determine verdict based on number of trusted sources
            if unique_count >= min_sources:
                verdict = 'Real'
                trust_boost = 15
                explanation = f'Verified by {unique_count} trusted news sources. '
            elif unique_count >= 2:
                verdict = 'Partially Correct'
                trust_boost = 5
                explanation = f'Found in {unique_count} trusted sources (minimum {min_sources} recommended for full verification). '
            elif unique_count == 1:
                verdict = 'Partially Correct'
                trust_boost = 0
                explanation = f'Only 1 trusted source found. Need at least {min_sources} sources for reliable verification. '
            else:
                verdict = 'Fake'
                trust_boost = -20
                explanation = f'No coverage found in trusted news sources. Claims without verification from reputable outlets are suspect. '

            return {
                'success': True,
                'sources': sources,
                'unique_source_count': unique_count,
                'verdict': verdict,
                'trust_boost': trust_boost,
                'explanation': explanation,
            }

        except requests.RequestException as e:
            logger.exception("News verification request failed")
            return {
                'success': False,
                'sources': [],
                'unique_source_count': 0,
                'verdict': None,
                'trust_boost': 0,
                'explanation': f'Could not reach news verification service: {str(e)[:80]}',
            }
