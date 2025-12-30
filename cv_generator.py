"""CV generation and customization"""

import asyncio
import copy
import pathlib
import tempfile
import yaml
from typing import Dict, Any, Tuple, Optional

import httpx

from config import Config, CVCLConfig
from rich.console import Console


class CVGenerator:
    """Generates customized CVs based on job requirements"""

    def __init__(self, config: Config, cvcl_config: Optional[CVCLConfig] = None, verbose: bool = False):
        self.config = config
        self.cvcl_config = cvcl_config or CVCLConfig.load()
        self.verbose = verbose
        self.console = Console()

    async def generate_cv(self, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Tuple[Dict[str, Any], pathlib.Path]:
        """Generate a customized CV based on job requirements and personal context"""
        # Load base CV template
        base_cv = await self._load_base_cv()

        # Customize CV content
        customized_cv = await self._customize_cv_content(base_cv, job_info, rag_context)

        # Save customized CV as YAML
        cv_yaml_file = await self._save_cv_yaml(customized_cv, job_info)

        # Generate PDF using RenderCV
        pdf_file = await self._generate_pdf(cv_yaml_file)

        return customized_cv, pdf_file

    async def _load_base_cv(self) -> Dict[str, Any]:
        """Load the base CV template - prefers global config, falls back to user template"""
        # Try global CV config first
        if self.cvcl_config.cv.base_cv_file.exists():
            try:
                with open(self.cvcl_config.cv.base_cv_file, 'r', encoding='utf-8') as f:
                    cv_data = yaml.safe_load(f)
                    if self.verbose:
                        self.console.print(f"[dim]Loaded global CV template: {self.cvcl_config.cv.base_cv_file}[/dim]")
                    return cv_data
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load global CV template: {str(e)}[/yellow]")

        # Fallback to user-specific template if it exists
        user_template_path = pathlib.Path(f"./users/{self.config.user_name}/cv_template.yaml")
        if user_template_path.exists():
            try:
                with open(user_template_path, 'r', encoding='utf-8') as f:
                    cv_data = yaml.safe_load(f)
                    if self.verbose:
                        self.console.print(f"[dim]Loaded user CV template: {user_template_path}[/dim]")
                    return cv_data
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load user CV template: {str(e)}[/yellow]")

        # Return a minimal CV structure if no templates exist
        if self.verbose:
            self.console.print("[dim]Using minimal CV template as fallback[/dim]")
        return self._get_minimal_cv_template()

    def _get_minimal_cv_template(self) -> Dict[str, Any]:
        """Return a minimal CV template structure"""
        return {
            'cv': {
                'name': 'Your Name',
                'location': 'Your Location',
                'email': 'your.email@example.com',
                'phone': '+46-70-123-4567',  # International format
                'website': 'https://yourwebsite.com',
                'sections': {
                    # Empty sections are not allowed, so we provide minimal valid entries
                    'experience': [{
                        'company': 'Company Name',
                        'position': 'Position Title',
                        'start_date': '2023-01',
                        'end_date': 'present',
                        'location': 'Location',
                        'highlights': ['Description of experience']
                    }],
                    'education': [{
                        'institution': 'University Name',
                        'area': 'Field of Study',
                        'degree': 'Degree',
                        'start_date': '2020-09',
                        'end_date': '2024-06',
                        'location': 'Location'
                    }],
                    'skills': [{
                        'label': 'Skills',
                        'details': 'Technical skills and competencies'
                    }],
                    'projects': [{
                        'name': 'Project Name',
                        'summary': 'Project description',
                        'highlights': ['Key achievements']
                    }]
                }
            },
            'design': {'theme': self.cvcl_config.cv.theme},
            'locale': {'language': 'en'},
            'rendercv_settings': {'date': '2025-12-28'}
        }

    async def _customize_cv_content(self, base_cv: Dict[str, Any], job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """Customize CV content based on job requirements and personal context"""
        customized_cv = copy.deepcopy(base_cv)

        # Customize headline if we have job context
        if job_info.get('title'):
            job_title = job_info['title']
            # Try to create a relevant headline
            headline = await self._generate_relevant_headline(job_title, rag_context)
            if headline:
                customized_cv['cv']['headline'] = headline

        # Prioritize and customize experience section
        if 'experience' in customized_cv['cv']['sections']:
            customized_cv['cv']['sections']['experience'] = await self._prioritize_experience(
                customized_cv['cv']['sections']['experience'],
                job_info,
                rag_context
            )

        # Customize skills section
        if 'skills' in customized_cv['cv']['sections']:
            customized_cv['cv']['sections']['skills'] = await self._prioritize_skills(
                customized_cv['cv']['sections']['skills'],
                job_info,
                rag_context
            )

        # Customize projects section
        if 'projects' in customized_cv['cv']['sections']:
            customized_cv['cv']['sections']['projects'] = await self._prioritize_projects(
                customized_cv['cv']['sections']['projects'],
                job_info,
                rag_context
            )

        # Validate content to ensure honesty (skip for minimal template)
        if customized_cv.get('cv', {}).get('name') != 'Your Name':
            validated_cv = self.validate_cv_content(customized_cv, rag_context)
            if self.verbose and validated_cv != customized_cv:
                self.console.print("[yellow]⚠️ Some content was removed during validation to ensure accuracy[/yellow]")
        else:
            # Skip validation for minimal template to preserve placeholder data
            validated_cv = customized_cv
            if self.verbose:
                self.console.print("[dim]Skipping validation for minimal template[/dim]")

        return validated_cv

    async def _generate_relevant_headline(self, job_title: str, rag_context: Dict[str, Any]) -> Optional[str]:
        """Generate a relevant headline based on job title and experience"""
        # Simple logic for now - can be enhanced with LLM
        job_title_lower = job_title.lower()

        # Look for relevant experience in context
        experience_items = rag_context.get('experience', [])
        if experience_items:
            # Use the most relevant experience to inform headline
            top_experience = experience_items[0]['content'] if experience_items else ""

            # Extract key skills/roles from experience
            if 'senior' in job_title_lower or 'lead' in job_title_lower:
                return f"Senior {job_title}"
            elif 'machine learning' in job_title_lower or 'ml' in job_title_lower:
                return "Machine Learning Engineer"
            elif 'data' in job_title_lower:
                return "Data Scientist / Engineer"
            elif 'software' in job_title_lower:
                return "Software Engineer"
            elif 'full stack' in job_title_lower:
                return "Full Stack Developer"

        return None  # Keep original headline

    async def _prioritize_experience(self, experiences: list, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> list:
        """Reorder and highlight experience based on job requirements"""
        if not experiences:
            return experiences

        job_description = job_info.get('description', '').lower()
        job_title = job_info.get('title', '').lower()

        # Score each experience item
        scored_experiences = []
        for exp in experiences:
            score = 0
            exp_text = str(exp).lower()

            # Check for keyword matches with job description
            keywords = self._extract_job_keywords(job_description)
            for keyword in keywords:
                if keyword in exp_text:
                    score += 1

            # Check for job title relevance
            if any(word in exp_text for word in job_title.split()):
                score += 2

            scored_experiences.append((score, exp))

        # Sort by score (highest first) and return experiences
        scored_experiences.sort(key=lambda x: x[0], reverse=True)
        return [exp for score, exp in scored_experiences]

    async def _prioritize_skills(self, skills: list, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> list:
        """Reorder skills based on job requirements"""
        if not skills:
            return skills

        job_description = job_info.get('description', '').lower()

        # Score skills based on job description mentions
        scored_skills = []
        for skill in skills:
            score = 0
            skill_text = str(skill).lower()

            if skill_text in job_description:
                score += 1

            scored_skills.append((score, skill))

        # Sort by relevance and return
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [skill for score, skill in scored_skills]

    async def _prioritize_projects(self, projects: list, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> list:
        """Reorder projects based on job requirements"""
        if not projects:
            return projects

        job_description = job_info.get('description', '').lower()

        # Score projects based on relevance to job
        scored_projects = []
        for project in projects:
            score = 0
            project_text = str(project).lower()

            # Check for technology matches
            tech_keywords = ['python', 'javascript', 'react', 'node', 'aws', 'docker', 'kubernetes', 'ml', 'ai']
            for tech in tech_keywords:
                if tech in project_text and tech in job_description:
                    score += 1

            scored_projects.append((score, project))

        # Sort by relevance
        scored_projects.sort(key=lambda x: x[0], reverse=True)
        return [project for score, project in scored_projects]

    def _extract_job_keywords(self, job_description: str) -> list:
        """Extract important keywords from job description"""
        # Common tech keywords
        keywords = [
            'python', 'javascript', 'java', 'c++', 'typescript', 'react', 'angular', 'vue',
            'node', 'django', 'flask', 'spring', 'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'machine learning', 'ai', 'data science', 'tensorflow', 'pytorch', 'sql',
            'mongodb', 'postgresql', 'mysql', 'git', 'agile', 'scrum', 'devops', 'ci/cd'
        ]

        found_keywords = []
        desc_lower = job_description.lower()

        for keyword in keywords:
            if keyword in desc_lower:
                found_keywords.append(keyword)

        return found_keywords

    async def _save_cv_yaml(self, cv_data: Dict[str, Any], job_info: Dict[str, Any]) -> pathlib.Path:
        """Save customized CV as YAML file"""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(cv_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            temp_file = pathlib.Path(f.name)

        if self.verbose:
            self.console.print(f"[dim]CV YAML saved to: {temp_file}[/dim]")

        return temp_file

    async def _generate_pdf(self, cv_yaml_file: pathlib.Path) -> pathlib.Path:
        """Generate PDF using RenderCV"""
        import subprocess
        import sys

        # Create output PDF path
        pdf_file = cv_yaml_file.with_suffix('.pdf')

        try:
            # Run rendercv command
            cmd = [
                'rendercv',
                'render', str(cv_yaml_file),
                '--pdf-path', str(pdf_file),
                '--dont-generate-markdown',
                '--dont-generate-html'
            ]

            if self.verbose:
                self.console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
                self.console.print(f"[dim]YAML file: {cv_yaml_file}[/dim]")

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=pathlib.Path.cwd())

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.console.print(f"[red]RenderCV error: {error_msg}[/red]")
                raise Exception(f"RenderCV failed: {error_msg}")

            if not pdf_file.exists():
                raise Exception("PDF file was not generated")

            if self.verbose:
                self.console.print(f"[dim]PDF generated: {pdf_file}[/dim]")

            return pdf_file

        except Exception as e:
            self.console.print(f"[red]Error generating PDF: {str(e)}[/red]")
            raise

    def validate_cv_content(self, cv_content: Dict[str, Any], rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate CV content to ensure honesty and accuracy.
        Removes any fabricated content that isn't supported by the RAG database.
        """
        validated_cv = copy.deepcopy(cv_content)

        # Extract all verified information from RAG context
        verified_skills = set()
        verified_experiences = []
        verified_projects = []
        verified_education = []

        if "skills" in rag_context:
            verified_skills.update(rag_context["skills"])

        if "experiences" in rag_context:
            verified_experiences = rag_context["experiences"]

        if "projects" in rag_context:
            verified_projects = rag_context["projects"]

        if "education" in rag_context:
            verified_education = rag_context["education"]

        # Validate and clean sections
        if "cv" in validated_cv and "sections" in validated_cv["cv"]:
            sections_dict = validated_cv["cv"]["sections"]
            for section_name, section_entries in sections_dict.items():
                section_type = section_name.lower()

                if section_type == "experience" and isinstance(section_entries, list):
                    # Keep only experiences that are verified
                    verified_entries = []
                    for entry in section_entries:
                        if self._is_experience_verified(entry, verified_experiences):
                            verified_entries.append(entry)
                    sections_dict[section_name] = verified_entries

                elif section_type == "projects" and isinstance(section_entries, list):
                    # Keep only projects that are verified
                    verified_entries = []
                    for entry in section_entries:
                        if self._is_project_verified(entry, verified_projects):
                            verified_entries.append(entry)
                    sections_dict[section_name] = verified_entries

                elif section_type == "education" and isinstance(section_entries, list):
                    # Keep only education that is verified
                    verified_entries = []
                    for entry in section_entries:
                        if self._is_education_verified(entry, verified_education):
                            verified_entries.append(entry)
                    sections_dict[section_name] = verified_entries

                elif section_type == "skills" and isinstance(section_entries, list):
                    # Keep only skills that are verified
                    verified_entries = []
                    for entry in section_entries:
                        if self._is_skill_verified(entry, verified_skills):
                            verified_entries.append(entry)
                    sections_dict[section_name] = verified_entries

        return validated_cv

    def _is_experience_verified(self, entry: Dict[str, Any], verified_experiences: list) -> bool:
        """Check if an experience entry is verified against RAG data"""
        entry_title = entry.get("position", "").lower()
        entry_company = entry.get("company", "").lower()

        for verified_exp in verified_experiences:
            if (entry_title in verified_exp.get("position", "").lower() or
                verified_exp.get("position", "").lower() in entry_title):
                if (entry_company in verified_exp.get("company", "").lower() or
                    verified_exp.get("company", "").lower() in entry_company):
                    return True
        return False

    def _is_project_verified(self, entry: Dict[str, Any], verified_projects: list) -> bool:
        """Check if a project entry is verified against RAG data"""
        entry_name = entry.get("name", "").lower()

        for verified_proj in verified_projects:
            if (entry_name in verified_proj.get("name", "").lower() or
                verified_proj.get("name", "").lower() in entry_name):
                return True
        return False

    def _is_education_verified(self, entry: Dict[str, Any], verified_education: list) -> bool:
        """Check if an education entry is verified against RAG data"""
        entry_degree = entry.get("degree", "").lower()
        entry_institution = entry.get("institution", "").lower()

        for verified_edu in verified_education:
            if (entry_degree in verified_edu.get("degree", "").lower() or
                verified_edu.get("degree", "").lower() in entry_degree):
                if (entry_institution in verified_edu.get("institution", "").lower() or
                    verified_edu.get("institution", "").lower() in entry_institution):
                    return True
        return False

    def _is_skill_verified(self, entry: Dict[str, Any], verified_skills: set) -> bool:
        """Check if a skill entry is verified against RAG data"""
        entry_name = entry.get("name", "").lower()

        for skill in verified_skills:
            if skill.lower() in entry_name or entry_name in skill.lower():
                return True
        return False
