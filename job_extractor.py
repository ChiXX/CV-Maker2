"""Job description extraction from URLs"""

import asyncio
import os
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

from langchain_openai import ChatOpenAI



JOB_EXTRACTION_PROMPT = """You are an expert job description analyst. Your task is to carefully extract and structure job posting information from web content.

CONTENT SOURCE: {url}
EXTRACTED TEXT FROM WEBPAGE:
{visible_text}

INSTRUCTIONS:
1. **Job Title**: Extract the exact job position title. Look for headings like "Job Title", "Position", or similar. If multiple titles appear, choose the most prominent one.

2. **Company Name**: Extract the company/organization name. Check for logos, headers, footers, or explicit mentions. If not found, you may infer from URL domain or context.

3. **Job Description**: Extract the complete job description including:
   - Role responsibilities and duties
   - Required qualifications and skills
   - Experience requirements
   - Education requirements
   - Benefits and compensation (if mentioned)
   - Application instructions
   - Any other relevant job details

IMPORTANT:
- If the content is not in English, translate it into English befor filing the JD
- Preserve technical terms, company names, and specific jargon in their original form when appropriate
- Remove irrelevant content like navigation menus, footers, ads, or meta information
- Be thorough but concise - include all relevant details without unnecessary repetition

OUTPUT FORMAT:
### Title:
[Job Title Here]

### Company:
[Company Name Here]

### JD:
[Complete job description text here, properly formatted in English]

### END

Only extract what's visible from the content or logically inferrable from the URL. If you cannot identify the content from the webpage, respond with:

### Title:
[UNKNOWN]

### Company:
[UNKNOWN]

### JD:
[UNKNOWN]

### END

"""


class JobExtractor:
    """Extracts job information from various job posting URLs"""

    def __init__(self, llm_config: dict = None, verbose: bool = False):
        self.verbose = verbose
        self.console = Console()
        self.llm_config = llm_config or {}

        # Initialize LangChain ChatOpenAI client for job extraction if API key is available
        api_key = os.getenv('OPENROUTER_API_KEY')
        self.chat_openai = ChatOpenAI(
            api_key=api_key,
            base_url=self.llm_config.get('base_url', 'google/gemini-2.0-flash-001'),
            model=self.llm_config.get('model', 'mistralai/mistral-small-3.1-24b-instruct:free'),
            temperature=self.llm_config.get('temperature', 0.1),
            max_tokens=self.llm_config.get('max_tokens', 2000)
        )

    async def extract_job_info(self, url: str) -> Dict[str, Any]:
        """Extract job information from a URL using LLM (simplified approach)"""
        if self.verbose:
            self.console.print(f"🌐 Fetching job page content: {url}")

        try:
            # Fetch HTML content
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            # Extract visible text from HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script, style, and noscript tags
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            # Get visible text
            raw_text = soup.get_text(separator="\n")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            visible_text = "\n".join(lines[:200])  # Limit to first 200 lines

            # Use LLM to extract structured information
            return await self._extract_with_llm(url, visible_text)

        except Exception as e:
            if self.verbose:
                self.console.print("❌ Failed to extract job information")
            return {
                'title': 'Unknown Position',
                'company': 'Unknown Company',
                'description': 'Unknown Job Description',
                'error': str(e)
            }


    async def _extract_with_llm(self, url: str, visible_text: str) -> Dict[str, Any]:
        """Use LLM to extract job information (exact approach from GitHub)"""

        try:
            prompt = JOB_EXTRACTION_PROMPT.format(
                url=url,
                visible_text=visible_text
            )

            if self.verbose:
                self.console.print("🤖 Calling LLM to extract JD information")

            # Use LangChain's invoke method
            response = await self.chat_openai.ainvoke(prompt)
            content = response.content

            jd, company, title = "", "", ""
            # Extract in the correct order: Title, Company, JD
            match_tt = re.search(r"### Title:\n(.*?)\n### Company:", content, re.DOTALL)
            match_co = re.search(r"### Company:\n(.*?)\n### JD:", content, re.DOTALL)
            match_jd = re.search(r"### JD:\n(.*?)\n### END", content, re.DOTALL)
            if match_tt:
                title = match_tt.group(1).strip()
            if match_co:
                company = match_co.group(1).strip()
            if match_jd:
                jd = match_jd.group(1).strip()
                
            if "[UNKNOWN]" in title or "[UNKNOWN]" in company or "[UNKNOWN]" in jd:
                if self.verbose:
                    self.console.print("❌ Failed to extract job information")
                return {
                    'title': 'Unknown Position',
                    'company': 'Unknown Company',
                    'description': 'Unknown Job Description',
                    'error': 'Failed to extract job information'
                }

            return {
                'title': title,
                'company': company,
                'description': jd
            }

        except Exception as e:
            if self.verbose:
                self.console.print("❌ Failed to extract job information")
            return {
                'title': 'Unknown Position',
                'company': 'Unknown Company',
                'description': 'Unknown Job Description'
            }

