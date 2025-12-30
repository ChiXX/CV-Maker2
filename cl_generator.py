"""Cover letter generation and customization"""

import asyncio
import os
import pathlib
import tempfile
import yaml
from typing import Dict, Any, Tuple, Optional

from config import Config, CVCLConfig
from langchain_openai import ChatOpenAI
from rich.console import Console


COVER_LETTER_GENERATION_PROMPT = """You are an expert cover letter writer. Your task is to create a compelling, professional cover letter tailored to a specific job opportunity.

JOB OPPORTUNITY:
- Title: {job_title}
- Company: {company}
- Description: {job_description}

APPLICANT INFORMATION:
- Name: {applicant_name}
- Experience Summary: {experience_summary}
- Skills: {skills_summary}

INSTRUCTIONS:
Create a professional cover letter that:

1. **Opening Paragraph**: Grab attention with a strong introduction that shows enthusiasm for the role and company. Mention how you found the position.

2. **Body Paragraphs**: Highlight 2-3 key qualifications and experiences that directly relate to the job requirements. Use specific examples and quantify achievements where possible.

3. **Company Connection**: Show you've researched the company and explain why you're interested in working there specifically.

4. **Closing Paragraph**: Reiterate your interest, mention next steps, and provide contact information.

5. **Professional Tone**: Use formal business language appropriate for the industry and role level.

IMPORTANT RULES:
- Keep the letter to 3-4 paragraphs (300-500 words total)
- NEVER fabricate experience, skills, or qualifications - only use information provided
- Focus on achievements and impact rather than just listing responsibilities
- Show enthusiasm and cultural fit
- Proofread for grammar and professionalism
- Use the applicant's actual name and reference real experiences

FORMAT: Return ONLY the main body paragraphs of the cover letter. Do NOT include any headers, addresses, dates, salutations (e.g. \"Dear ...\"), or closing signatures. Only return the plain content paragraphs that belong in the body of the letter."""


class CoverLetterGenerator:
    """Generates customized cover letters based on job requirements"""

    def __init__(self, config: Config, cvcl_config: Optional[CVCLConfig] = None, verbose: bool = False):
        self.config = config
        self.cvcl_config = cvcl_config or CVCLConfig()
        self.verbose = verbose
        self.console = Console()

        # Initialize LangChain ChatOpenAI client for cover letter generation
        llm_config = getattr(config, 'llm_config', {}) or {}
        api_key = os.getenv('OPENROUTER_API_KEY')
        self.chat_openai = ChatOpenAI(
            api_key=api_key,
            base_url=llm_config.get('base_url', 'https://openrouter.ai/api/v1'),
            model=llm_config.get('model', 'mistralai/mistral-small-3.1-24b-instruct:free'),
            temperature=llm_config.get('temperature', 0.1),
            max_tokens=llm_config.get('max_tokens', 2000)
        )

    async def generate_cover_letter(self, job_info: Dict[str, Any], rag_context: Dict[str, Any], cv_content: Dict[str, Any]) -> Tuple[str, pathlib.Path]:
        """Generate a customized cover letter"""
        try:
            # Validate required data
            if not job_info or not isinstance(job_info, dict):
                raise ValueError("Job information is required for cover letter generation")

            if not cv_content or not isinstance(cv_content, dict):
                raise ValueError("CV content is required for cover letter generation")

            # Generate cover letter content
            cover_letter_text = await self._generate_cover_letter_content(job_info, rag_context, cv_content)
            if not cover_letter_text or not cover_letter_text.strip():
                raise ValueError("Failed to generate cover letter content")

            # Create a temporary text file
            cover_letter_file = await self._create_cover_letter_file(cover_letter_text, job_info)

            # Convert to PDF
            pdf_file = await self._convert_to_pdf(cover_letter_file, job_info)

            # Verify PDF was created successfully
            if not pdf_file.exists() or pdf_file.stat().st_size == 0:
                raise ValueError("PDF file was not created successfully")

            return cover_letter_text, pdf_file

        except Exception as e:
            error_msg = f"Cover letter generation failed: {str(e)}"
            if self.verbose:
                self.console.print(f"[red]{error_msg}[/red]")
            raise Exception(error_msg)

    async def _generate_cover_letter_content(self, job_info: Dict[str, Any], rag_context: Dict[str, Any], cv_content: Dict[str, Any]) -> str:
        """Generate cover letter content using AI"""
        try:
            # Load user's personal information
            user_personal_info = self._load_user_personal_info()

            # Extract key information
            company = str(job_info.get('company', 'the company'))
            job_title = str(job_info.get('title', 'the position'))
            job_description = str(job_info.get('description', '')[:1500])  # Limit length

            applicant_name = str(user_personal_info.get('name', 'Your Name'))
            email = str(user_personal_info.get('email', ''))
            phone_raw = str(user_personal_info.get('phone', ''))
            # Format phone number (assuming Swedish format for +46 numbers)
            if phone_raw.startswith('+46'):
                phone = f"0{phone_raw[3:5]}-{phone_raw[5:8]} {phone_raw[8:]}"
            else:
                phone = phone_raw
            location = user_personal_info.get('location', {})
            city = location.get('city', '') if isinstance(location, dict) else ''
            country = location.get('country', '') if isinstance(location, dict) else ''
            address = f"{city}, {country}".strip(', ') if city or country else ''
            website = str(user_personal_info.get('website', '')).replace('https://', '')

            # Prepare experience and skills summaries from RAG context
            experience_items = rag_context.get('experiences', []) or rag_context.get('experience', [])
            experience_summary = ""
            if experience_items:
                # Take top 2 experiences and summarize
                top_experiences = experience_items[:2]
                experience_summaries = []
                for exp in top_experiences:
                    if isinstance(exp, dict):
                        company_name = exp.get('company', 'Company')
                        position_name = exp.get('position', 'Position')
                        exp_summary = f"{position_name} at {company_name}"
                        if exp.get('highlights') or exp.get('content'):
                            highlights = exp.get('highlights') or exp.get('content', '')[:100]
                            exp_summary += f": {highlights}"
                        experience_summaries.append(exp_summary)
                    else:
                        experience_summaries.append(str(exp)[:150])
                experience_summary = "; ".join(experience_summaries)

            skills_items = rag_context.get('skills', [])
            skills_summary = ""
            if skills_items:
                # Take top 5 skills
                top_skills = []
                for skill in skills_items[:5]:
                    if isinstance(skill, dict):
                        skill_name = skill.get('name') or skill.get('content') or str(skill)
                    else:
                        skill_name = str(skill)
                    top_skills.append(skill_name[:50])  # Limit length
                skills_summary = ", ".join(top_skills)

            # Format the prompt with actual data
            prompt = COVER_LETTER_GENERATION_PROMPT.format(
                job_title=job_title,
                company=company,
                job_description=job_description,
                applicant_name=applicant_name,
                experience_summary=experience_summary or "Professional experience in relevant field",
                skills_summary=skills_summary or "Technical and professional skills"
            )

            if self.verbose:
                self.console.print("🤖 Generating cover letter with AI")

            response = await self.chat_openai.ainvoke(prompt)
            cover_letter_body = response.content.strip()
            # Remove any leading salutation the model might include (e.g., "Dear Hiring Manager,")
            import re
            # Remove any leading salutations the model might include (handles CRLF and LF)
            cover_letter_body = re.sub(r'^(?:\s*Dear[^\r\n]*[\r\n]+)+', '', cover_letter_body, flags=re.I)

            # Format current date
            from datetime import datetime
            current_date = datetime.now().strftime("%B %d, %Y")

            # Format with applicant's name and contact info
            contact_info = []
            if address:
                contact_info.append(address)
            if email:
                contact_info.append(email)
            if phone:
                contact_info.append(phone)
            if website:
                contact_info.append(website)

            # Try to get company location from job info or use a placeholder
            company_location = job_info.get('location', 'Stockholm, Sweden')

            # Use double-newlines between header lines so the PDF renderer treats each as its own paragraph
            header_block = '\n\n'.join(contact_info) if contact_info else ''

            formatted_cover_letter = f"""{applicant_name}

{header_block}

{current_date}

Hiring Manager

{company}

{company_location}

Dear Hiring Manager,

{cover_letter_body}

Sincerely,

{applicant_name}"""

            if self.verbose:
                self.console.print("✅ Cover letter generated successfully")

            return formatted_cover_letter

        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]AI cover letter generation failed: {str(e)}, using template[/yellow]")

            # Fallback to simple template with real user info
            user_personal_info = self._load_user_personal_info()
            applicant_name = str(user_personal_info.get('name', 'Your Name'))
            company = str(job_info.get('company', 'the company'))
            job_title = str(job_info.get('title', 'the position'))

            # Get user contact info
            email = str(user_personal_info.get('email', ''))
            phone_raw = str(user_personal_info.get('phone', ''))
            # Format phone number (assuming Swedish format for +46 numbers)
            if phone_raw.startswith('+46'):
                phone = f"0{phone_raw[3:5]}-{phone_raw[5:8]} {phone_raw[8:]}"
            else:
                phone = phone_raw
            location = user_personal_info.get('location', {})
            city = location.get('city', '') if isinstance(location, dict) else ''
            country = location.get('country', '') if isinstance(location, dict) else ''
            address = f"{city}, {country}".strip(', ') if city or country else ''
            website = str(user_personal_info.get('website', '')).replace('https://', '')

            # Format current date
            from datetime import datetime
            current_date = datetime.now().strftime("%B %d, %Y")

            # Format contact info
            contact_info = []
            if address:
                contact_info.append(address)
            if email:
                contact_info.append(email)
            if phone:
                contact_info.append(phone)
            if website:
                contact_info.append(website)

            # Try to get company location from job info or use a placeholder
            company_location = job_info.get('location', 'Stockholm, Sweden')

            # Use double-newlines between header lines so the PDF renderer treats each as its own paragraph
            header_block = '\n\n'.join(contact_info) if contact_info else ''

            return f"""{applicant_name}

{header_block}

{current_date}

Hiring Manager

{company}

{company_location}

Dear Hiring Manager,

I am writing to express my interest in the {job_title} position at {company}. I am excited about the opportunity to contribute to your team.

Thank you for considering my application.

Sincerely,

{applicant_name}"""


    async def _create_cover_letter_file(self, content: str, job_info: Dict[str, Any]) -> pathlib.Path:
        """Create a text file with the cover letter content"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = pathlib.Path(f.name)

        if self.verbose:
            self.console.print(f"[dim]Cover letter saved to: {temp_file}[/dim]")

        return temp_file

    async def _convert_to_pdf(self, text_file: pathlib.Path, job_info: Dict[str, Any]) -> pathlib.Path:
        """Convert text cover letter to PDF using reportlab"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.units import inch
            # Note: TA_LEFT = 0, TA_JUSTIFIED = 4

            # Create output PDF path
            pdf_file = text_file.with_suffix('.pdf')

            # Read the cover letter content
            with open(text_file, 'r', encoding='utf-8') as content_file:
                content = content_file.read()

            # Create PDF document
            doc = SimpleDocTemplate(
                str(pdf_file),
                pagesize=A4,
                leftMargin=1*inch,
                rightMargin=1*inch,
                topMargin=1*inch,
                bottomMargin=1*inch
            )
            styles = getSampleStyleSheet()

            # Create custom styles
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=11,
                leading=14,
                alignment=4,  # TA_JUSTIFIED
                spaceAfter=6
            )

            header_style = ParagraphStyle(
                'Header',
                parent=styles['Normal'],
                fontSize=11,
                leading=13,
                alignment=0,  # TA_LEFT
                spaceAfter=3
            )

            signature_style = ParagraphStyle(
                'Signature',
                parent=styles['Normal'],
                fontSize=11,
                leading=13,
                alignment=0  # TA_LEFT
            )

            # Split content into lines and process each part
            lines = content.split('\n')
            paragraphs = []
            current_paragraph = []

            for line in lines:
                line = line.strip()
                if not line:
                    # Empty line - finish current paragraph
                    if current_paragraph:
                        para_text = ' '.join(current_paragraph)
                        if para_text:
                            paragraphs.append(Paragraph(para_text, normal_style))
                        current_paragraph = []
                    paragraphs.append(Spacer(1, 0.15 * inch))
                else:
                    # Check for specific sections
                    if line in ['Sincerely,', 'Best regards,', 'Regards,'] or line.startswith('Sincerely,'):
                        # This is the closing
                        if current_paragraph:
                            para_text = ' '.join(current_paragraph)
                            if para_text:
                                paragraphs.append(Paragraph(para_text, normal_style))
                            current_paragraph = []
                        paragraphs.append(Spacer(1, 0.3 * inch))
                        paragraphs.append(Paragraph(line, signature_style))
                    elif any(keyword in line.lower() for keyword in ['dear hiring manager', 'dear ', 'hello']):
                        # Salutation
                        if current_paragraph:
                            para_text = ' '.join(current_paragraph)
                            if para_text:
                                paragraphs.append(Paragraph(para_text, normal_style))
                            current_paragraph = []
                        paragraphs.append(Paragraph(line, header_style))
                    elif '@' in line or any(word in line.lower() for word in ['street', 'avenue', 'road', 'city', 'state', 'zip', 'phone', 'email']):
                        # Address/contact info - use header style
                        if current_paragraph:
                            para_text = ' '.join(current_paragraph)
                            if para_text:
                                paragraphs.append(Paragraph(para_text, normal_style))
                            current_paragraph = []
                        paragraphs.append(Paragraph(line, header_style))
                    else:
                        # Regular content
                        current_paragraph.append(line)

            # Add any remaining content
            if current_paragraph:
                para_text = ' '.join(current_paragraph)
                if para_text:
                    paragraphs.append(Paragraph(para_text, normal_style))

            # Build PDF
            doc.build(paragraphs)

            if self.verbose:
                self.console.print(f"[dim]Cover letter PDF generated: {pdf_file}[/dim]")

            return pdf_file

        except ImportError as e:
            self.console.print(f"[red]reportlab not available for PDF generation: {str(e)}[/red]")
            raise Exception("reportlab library required for PDF generation. Install with: pip install reportlab")

        except Exception as e:
            self.console.print(f"[red]Error generating cover letter PDF: {str(e)}[/red]")
            raise

    def _load_user_personal_info(self) -> Dict[str, Any]:
        """Load user's personal information from file"""
        try:
            # Get user paths from config
            user_paths = self.config.user_paths
            personal_info_file = user_paths["personal_info"]

            if personal_info_file.exists():
                with open(personal_info_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                if self.verbose:
                    self.console.print(f"[yellow]Warning: Personal info file not found: {personal_info_file}[/yellow]")
                return {}
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not load personal info: {str(e)}[/yellow]")
            return {}

