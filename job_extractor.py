"""Job description extraction from URLs"""

import asyncio
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

from translation import TranslationService
from config import Config


class JobExtractor:
    """Extracts job information from various job posting URLs"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.console = Console()
        self.translation_service = TranslationService()

        # Common selectors for different job sites
        self.selectors = {
            'linkedin': {
                'title': ['h1[data-test-id="hero-job-title"]', 'h1.job-title', '.job-title'],
                'company': ['span[data-test-id="hero-company"]', '.company-name', '.job-company'],
                'location': ['span[data-test-id="hero-job-location"]', '.job-location', '.location'],
                'description': ['div[data-test-id="hero-job-description"]', '.job-description', '.description'],
            },
            'indeed': {
                'title': ['h1.jobsearch-JobMetadataHeader-title', '.job-title'],
                'company': ['div[data-company-name="true"]', '.company-name'],
                'location': ['div[data-testid="job-location"]', '.job-location'],
                'description': ['div[data-testid="job-description"]', '#jobDescriptionText'],
            },
            'glassdoor': {
                'title': ['h1[data-test="job-title"]', '.job-title'],
                'company': ['span[data-test="employer-name"]', '.company-name'],
                'location': ['span[data-test="location"]', '.location'],
                'description': ['div[data-test="job-description"]', '.job-description'],
            },
            'generic': {
                'title': ['h1', 'title'],
                'company': ['.company', '.employer', '[data-company]'],
                'location': ['.location', '.job-location', '[data-location]'],
                'description': ['.description', '.job-description', '#description', '[data-description]'],
            }
        }

    async def extract_job_info(self, url: str) -> Dict[str, Any]:
        """Extract job information from a URL"""
        if self.verbose:
            self.console.print(f"[dim]Fetching URL: {url}[/dim]")

        try:
            # Fetch webpage content
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            content = response.text
            soup = BeautifulSoup(content, 'html.parser')

            # Determine site type and extract info
            site_type = self._determine_site_type(url)
            job_info = self._extract_with_selectors(soup, site_type)

            # Add URL and clean up extracted data
            job_info['url'] = url
            job_info['site_type'] = site_type

            # Handle multi-language content
            job_info = await self._process_multilanguage_content(job_info)

            if self.verbose:
                self.console.print(f"[dim]Extracted: {job_info.get('title', 'Unknown')} at {job_info.get('company', 'Unknown')}[/dim]")

            return job_info

        except Exception as e:
            self.console.print(f"[red]Error extracting job info: {str(e)}[/red]")
            # Return basic info even if extraction fails
            return {
                'url': url,
                'title': 'Unknown Position',
                'company': 'Unknown Company',
                'location': 'Unknown Location',
                'description': f'Failed to extract job description from {url}',
                'error': str(e)
            }

    def _determine_site_type(self, url: str) -> str:
        """Determine the type of job site from URL"""
        domain = urlparse(url).netloc.lower()

        if 'linkedin.com' in domain:
            return 'linkedin'
        elif 'indeed.com' in domain:
            return 'indeed'
        elif 'glassdoor.com' in domain:
            return 'glassdoor'
        else:
            return 'generic'

    def _extract_with_selectors(self, soup: BeautifulSoup, site_type: str) -> Dict[str, str]:
        """Extract job information using site-specific selectors"""
        selectors = self.selectors.get(site_type, self.selectors['generic'])
        job_info = {}

        for field, selector_list in selectors.items():
            for selector in selector_list:
                try:
                    element = soup.select_one(selector)
                    if element:
                        # Get text content and clean it up
                        text = element.get_text(strip=True)
                        cleaned = self._clean_text(text)
                        # Only accept cleaned, non-empty text (avoid cookie banners / popups)
                        if cleaned and len(cleaned) > 0:
                            job_info[field] = cleaned
                            break
                except Exception:
                    continue

        # Fallback: try to extract from page title
        if 'title' not in job_info:
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # Try to extract job title from page title
                job_info['title'] = self._extract_title_from_page_title(title_text)

        return job_info

    def _clean_text(self, text: str) -> str:
        """Clean extracted text content"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove common unwanted strings (including cookie/banner phrases)
        unwanted_patterns = [
            r'View job details',
            r'Apply now',
            r'Save job',
            r'Report job',
            r'Share job',
            r'Select which cookies you accept',
            r'Accept all cookies',
            r'Manage cookies',
            r'Cookie settings',
            r'Cookie policy',
            r'We use cookies',
        ]

        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return text.strip()

    def _extract_title_from_page_title(self, page_title: str) -> str:
        """Try to extract job title from page title"""
        # Common patterns: "Job Title | Company - Site"
        # or "Job Title at Company | Site"

        # Remove site suffixes
        title = re.sub(r'\s*[-|]\s*(indeed|linkedin|glassdoor|monster).*', '', page_title, flags=re.IGNORECASE)

        # Try to extract job title before company name
        match = re.search(r'^([^|]+?)\s*(?:at|@|[-|])\s*(.+)$', title)
        if match:
            return match.group(1).strip()

        return title.strip()

    async def _process_multilanguage_content(self, job_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process multi-language job descriptions"""
        description = job_info.get('description', '')

        if not description:
            return job_info

        # Detect language and translate if needed
        detected_lang = self._detect_language(description)

        # If Swedish, translate to English
        if detected_lang == 'sv':
            if self.verbose:
                self.console.print("[dim]Detected Swedish content, translating to English...[/dim]")

            translated_desc = await self.translation_service.translate_to_english(description)
            if translated_desc:
                job_info['original_description'] = description
                job_info['description'] = translated_desc
                job_info['original_language'] = 'sv'
                job_info['translated'] = True
        else:
            job_info['original_language'] = detected_lang or 'unknown'
            job_info['translated'] = False

        return job_info

    def _detect_language(self, text: str) -> Optional[str]:
        """Simple language detection based on common words"""
        # Swedish indicators
        swedish_words = ['och', 'att', 'är', 'för', 'med', 'som', 'den', 'det', 'vi', 'på', 'av', 'eller']
        # Chinese indicators (simplified check)
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)

        text_lower = text.lower()

        # Check for Swedish
        swedish_count = sum(1 for word in swedish_words if word in text_lower)
        if swedish_count >= 2:
            return 'sv'

        # Check for Chinese
        if len(chinese_chars) > len(text) * 0.1:  # More than 10% Chinese characters
            return 'zh'

        # Default to English
        return 'en'
