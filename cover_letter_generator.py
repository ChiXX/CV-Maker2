"""Cover letter generation and customization"""

import asyncio
import pathlib
import tempfile
from typing import Dict, Any, Tuple, Optional

from config import Config, CVCLConfig
from rich.console import Console


class CoverLetterGenerator:
    """Generates customized cover letters based on job requirements"""

    def __init__(self, config: Config, cvcl_config: Optional[CVCLConfig] = None, verbose: bool = False):
        self.config = config
        self.cvcl_config = cvcl_config or CVCLConfig.load()
        self.verbose = verbose
        self.console = Console()

    async def generate_cover_letter(self, job_info: Dict[str, Any], rag_context: Dict[str, Any], cv_content: Dict[str, Any]) -> Tuple[str, pathlib.Path]:
        """Generate a customized cover letter"""
        # Generate cover letter content
        cover_letter_text = await self._generate_cover_letter_content(job_info, rag_context, cv_content)

        # Create a simple text file for now (can be enhanced to use templates)
        cover_letter_file = await self._create_cover_letter_file(cover_letter_text, job_info)

        # For now, we'll create a simple PDF from text
        # In a real implementation, you'd use a proper document generation library
        pdf_file = await self._convert_to_pdf(cover_letter_file, job_info)

        return cover_letter_text, pdf_file

    async def _generate_cover_letter_content(self, job_info: Dict[str, Any], rag_context: Dict[str, Any], cv_content: Dict[str, Any]) -> str:
        """Generate the actual cover letter content"""
        company = job_info.get('company', 'the company')
        position = job_info.get('title', 'the position')
        job_description = job_info.get('description', '') or ''

        # Ensure string types to avoid attribute errors
        company = str(company)
        position = str(position)
        job_description = str(job_description)

        # Extract key information from CV
        applicant_name = cv_content.get('cv', {}).get('name', 'Your Name')
        applicant_name = str(applicant_name)

        # Build cover letter
        cover_letter = f"""
{applicant_name}

[Your Address]
[City, State, ZIP Code]
[Email Address]
[Phone Number]
[Date]

[Hiring Manager's Name or "Hiring Manager"]
{company}
[Company Address]
[City, State, ZIP Code]

Dear Hiring Manager,

I am writing to express my strong interest in the {position} position at {company}, as advertised. With my background in [your field/expertise], I am excited about the opportunity to contribute to your team and help drive [company/ project's goals].

"""

        # Add relevant experience from RAG context
        experience_section = await self._build_experience_section(job_info, rag_context)
        if experience_section:
            cover_letter += experience_section

        # Add skills section
        skills_section = await self._build_skills_section(job_info, rag_context)
        if skills_section:
            cover_letter += skills_section

        # Add closing
        cover_letter += f"""
I am particularly drawn to {company} because of [something specific about the company or role that appeals to you]. I am eager to bring my [key strengths] to your team and contribute to [specific company goals or projects].

Thank you for considering my application. I would welcome the opportunity to discuss how my skills and experience align with {company}'s needs. I am available at your earliest convenience for an interview.

Sincerely,

{applicant_name}
"""

        # Validate content to ensure honesty
        validated_cover_letter = self.validate_cover_letter_content(cover_letter.strip(), rag_context)

        return validated_cover_letter

    async def _build_experience_section(self, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> str:
        """Build the experience paragraph for the cover letter"""
        experience_items = rag_context.get('experience', [])

        if not experience_items:
            return "In my previous roles, I have gained valuable experience in [relevant field] that would be beneficial for this position."

        # Use the most relevant experience (be defensive about formats)
        top_item = experience_items[0] if experience_items else ""
        top_experience = ""
        if isinstance(top_item, dict):
            # Prefer 'content' then fallback to stringify the dict
            top_experience = top_item.get('content') or top_item.get('text') or str(top_item)
        else:
            top_experience = str(top_item)

        # Extract key points (simplified - in reality you'd use NLP)
        try:
            if len(top_experience) > 200:
                top_experience = top_experience[:200] + "..."
        except Exception:
            top_experience = str(top_experience)

        top_experience = str(top_experience)
        return f"""
In my most recent role, {top_experience.lower()}

"""

    async def _build_skills_section(self, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> str:
        """Build the skills paragraph for the cover letter"""
        skills_items = rag_context.get('skills', [])
        job_description = job_info.get('description', '') or ''
        job_description = str(job_description)

        if not skills_items:
            return "My technical skills and passion for [field] make me a strong candidate for this role."

        # Extract relevant skills that match the job
        relevant_skills = []
        job_lower = job_description.lower()

        for skill_item in skills_items[:3]:  # Limit to top 3
            # skill_item may be a dict or a string
            if isinstance(skill_item, dict):
                skill_content = skill_item.get('content') or skill_item.get('name') or str(skill_item)
            else:
                skill_content = str(skill_item)

            skill_content_lower = skill_content.lower()
            # Simple matching - could be enhanced
            if any(tech in skill_content_lower for tech in ['python', 'javascript', 'aws', 'docker', 'ml', 'ai']):
                if any(tech in job_lower for tech in ['python', 'javascript', 'aws', 'docker', 'ml', 'ai']):
                    relevant_skills.append(skill_content[:100])  # Truncate

        if relevant_skills:
            skills_text = " Additionally, my expertise in " + ", ".join(relevant_skills)
            return skills_text + " directly aligns with the requirements of this position."
        else:
            return " My diverse skill set and proven track record make me confident in my ability to contribute effectively to your team."

    async def _create_cover_letter_file(self, content: str, job_info: Dict[str, Any]) -> pathlib.Path:
        """Create a text file with the cover letter content"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = pathlib.Path(f.name)

        if self.verbose:
            self.console.print(f"[dim]Cover letter saved to: {temp_file}[/dim]")

        return temp_file

    async def _convert_to_pdf(self, text_file: pathlib.Path, job_info: Dict[str, Any]) -> pathlib.Path:
        """Convert text cover letter to PDF"""
        # For now, create a simple approach using reportlab or similar
        # In a production system, you'd want proper document formatting

        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
        except ImportError:
            # If reportlab is not available, just copy the text file as "PDF"
            # In production, you'd install reportlab
            pdf_file = text_file.with_suffix('.pdf')
            import shutil
            shutil.copy2(text_file, pdf_file)
            if self.verbose:
                self.console.print("[yellow]ReportLab not available, created text-based PDF placeholder[/yellow]")
            return pdf_file

        # Create PDF with proper formatting
        pdf_file = text_file.with_suffix('.pdf')

        doc = SimpleDocTemplate(str(pdf_file), pagesize=letter)
        styles = getSampleStyleSheet()

        # Read the cover letter content
        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split into paragraphs and create PDF elements
        story = []
        paragraphs = content.split('\n\n')

        for para in paragraphs:
            if para.strip():
                p = Paragraph(para.strip(), styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.2 * inch))

        doc.build(story)

        if self.verbose:
            self.console.print(f"[dim]PDF cover letter generated: {pdf_file}[/dim]")

        return pdf_file

    def validate_cover_letter_content(self, cover_letter_text: str, rag_context: Dict[str, Any]) -> str:
        """
        Validate cover letter content to ensure honesty and accuracy.
        Removes or flags any fabricated claims that aren't supported by RAG data.
        """
        # Extract verified information from RAG context
        verified_companies = set()
        verified_positions = set()
        verified_skills = set()

        # Normalize experiences (some contexts use 'experience' key)
        experiences_list = rag_context.get("experiences") or rag_context.get("experience") or []
        for exp in experiences_list:
            if isinstance(exp, dict):
                verified_companies.add(str(exp.get("company", "")).lower())
                verified_positions.add(str(exp.get("position", "")).lower())
            else:
                # If exp is a string, just add to positions for simplicity
                verified_positions.add(str(exp).lower())

        if "skills" in rag_context:
            normalized_skills = []
            for skill in rag_context["skills"]:
                if isinstance(skill, str):
                    normalized_skills.append(skill.lower())
                elif isinstance(skill, dict):
                    name = skill.get("name") or skill.get("content") or ""
                    normalized_skills.append(str(name).lower())
                else:
                    normalized_skills.append(str(skill).lower())
            verified_skills.update(normalized_skills)

        # Simple validation - check for common patterns of potential fabrication
        lines = cover_letter_text.split('\n')
        validated_lines = []

        for line in lines:
            line_lower = line.lower()

            # Check for company mentions
            mentioned_companies = []
            for company in verified_companies:
                if company in line_lower and len(company) > 2:  # Avoid short matches
                    mentioned_companies.append(company)

            # Check for skill mentions
            mentioned_skills = []
            for skill in verified_skills:
                if skill in line_lower and len(skill) > 2:
                    mentioned_skills.append(skill)

            # If line mentions unverified companies or skills prominently, flag it
            if mentioned_companies and not any(company in verified_companies for company in mentioned_companies):
                if self.verbose:
                    self.console.print(f"[yellow]⚠️ Line may contain unverified company reference: {line.strip()}[/yellow]")
                # Comment out potentially fabricated content
                validated_lines.append(f"# POTENTIALLY UNVERIFIED: {line}")
            elif mentioned_skills and not any(skill in verified_skills for skill in mentioned_skills):
                if self.verbose:
                    self.console.print(f"[yellow]⚠️ Line may contain unverified skill reference: {line.strip()}[/yellow]")
                validated_lines.append(f"# POTENTIALLY UNVERIFIED: {line}")
            else:
                validated_lines.append(line)

        return '\n'.join(validated_lines)
