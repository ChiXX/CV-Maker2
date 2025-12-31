"""CV generation and customization"""

import asyncio
import copy
import json
import os
import pathlib
import tempfile
import yaml
from typing import Dict, Any, Tuple, Optional

from config import Config, CVCLConfig
from langchain_openai import ChatOpenAI
from rich.console import Console

CV_CUSTOMIZATION_PROMPT = """You are an expert CV customization consultant. Your task is to create a CV data structure based on a job opportunity and personal information.

JOB OPPORTUNITY:
- Title: {job_title}
- Company: {company}
- Description: {job_description}

PERSONAL CONTEXT (verified information only):
Skills: {skills}
Experience: {experience}
Projects: {projects}
Education: {education}

TASK: Generate a personalized CV data structure as a Python dictionary. The output should be valid JSON that can be parsed with json.loads().

REQUIRED OUTPUT STRUCTURE (Python dict/JSON):
{{
  "name": "Full Name",
  "headline": "1-2 sentences highlighting relevant experience for this job",
  "location": "City, State/Country",
  "email": "email@domain.com",
  "photo": null or "path/to/photo",
  "phone": null or "phone number",
  "website": "https://website.com",
  "social_networks": [
    {{"network": "LinkedIn", "username": "username"}},
    {{"network": "GitHub", "username": "username"}}
  ],
  "custom_connections": [],
  "sections": {{
    "education": [
      {{
        "institution": "University Name",
        "area": "Field of Study",
        "degree": "Degree Type",
        "date": null,
        "start_date": "YYYY-MM",
        "end_date": "YYYY-MM" or "present",
        "location": "City, Country",
        "summary": null,
        "highlights": ["Achievement 1", "Achievement 2"]
      }}
    ],
    "experience": [
      {{
        "company": "Company Name",
        "position": "Job Title",
        "date": null,
        "start_date": "YYYY-MM",
        "end_date": "YYYY-MM" or "present",
        "location": "City, State/Country",
        "summary": null,
        "highlights": ["Achievement 1", "Achievement 2", "Achievement 3"]
      }}
    ],
    "projects": [
      {{
        "name": "Project Name",
        "date": "YYYY" or null,
        "start_date": "YYYY-MM" or null,
        "end_date": "YYYY-MM" or "present" or null,
        "location": null,
        "summary": "Brief description",
        "highlights": ["Achievement 1", "Achievement 2"]
      }}
    ],
    "skills": [
      {{
        "label": "Category Name",
        "details": "skill1, skill2, skill3"
      }}
    ],
  }}
}}

OUTPUT REQUIREMENTS:
- Return ONLY valid JSON that can be parsed with json.loads()
- Use YYYY-MM format for all dates
- NEVER fabricate information - only use provided personal context
- For fields with no data, use null instead of empty strings
- Ensure all required fields are present even if empty
- **CRITICAL**: name field MUST NOT be null - use a placeholder name if none provided
- **CRITICAL**: All start_date and end_date fields MUST NOT be null - use reasonable estimates based on provided context
- **CRITICAL**: For social_networks, if network is not null, username MUST NOT be null

CONTENT GUIDELINES:
- **name**: REQUIRED - cannot be null, use provided name or reasonable placeholder
- **headline**: 1-2 sentences highlighting relevant experience for this job
- **experience**: 2-4 entries with achievements matching job description, ALL entries must have valid start_date and end_date
- **education**: 1-2 entries with relevant achievements, ALL entries must have valid start_date and end_date
- **projects**: 2-3 entries showing technical skills, ALL entries with dates must have valid start_date and end_date
- **skills**: 3-5 categories prioritizing job-relevant skills
- **social_networks**: Only include entries where both network AND username are provided and not null"""


class CVGenerator:
    """Generates customized CVs based on job requirements"""

    def __init__(self, config: Config, cvcl_config: Optional[CVCLConfig] = None, verbose: bool = False):
        self.config = config
        self.cvcl_config = cvcl_config or CVCLConfig()
        self.verbose = verbose
        self.console = Console()

        # Initialize LangChain ChatOpenAI client for CV customization
        llm_config = getattr(config, 'llm_config', {}) or {}
        api_key = os.getenv('OPENROUTER_API_KEY')
        self.chat_openai = ChatOpenAI(
            api_key=api_key,
            base_url=llm_config.get('base_url', 'https://openrouter.ai/api/v1'),
            model=llm_config.get('model', 'deepseek/deepseek-v3.2'),
            temperature=llm_config.get('temperature', 0.1),
            max_tokens=llm_config.get('max_tokens', 4000)
        )

    async def generate_cv(self, job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Tuple[Dict[str, Any], pathlib.Path]:
        """Generate a customized CV based on job requirements and personal context"""
        # Load base CV template
        base_cv = await self._load_base_cv()

        # Customize CV content
        customized_cv = await self._customize_cv_content(base_cv, job_info, rag_context)        

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(customized_cv, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            temp_file = pathlib.Path(f.name)

        # Generate PDF using RenderCV
        pdf_file = await self._generate_pdf(temp_file)

        return customized_cv, pdf_file

    async def _load_base_cv(self) -> Dict[str, Any]:
        """Load the base CV template from the templates directory"""
        script_dir = pathlib.Path(__file__).parent
        template_path = script_dir / "templates" / "cv.yaml"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                cv_data = yaml.safe_load(f)
                if self.verbose:
                    self.console.print(f"[dim]Loaded CV template: {template_path}[/dim]")
                return cv_data
        except Exception as e:
            error_msg = f"Failed to load CV template from {template_path}: {str(e)}"
            if self.verbose:
                self.console.print(f"[red]{error_msg}[/red]")
            raise Exception(error_msg)


    async def _customize_cv_content(self, base_cv: Dict[str, Any], job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """Customize CV content using AI based on job requirements and personal context"""
        # Use AI to generate the CV section dict
        cv_dict = await self._customize_cv_with_ai(base_cv, job_info, rag_context)
               
        self._validate_cv_dict(cv_dict)
        # Merge with template: use generated CV dict for cv section, keep rest from template
        merged_cv = {
            'cv': cv_dict,
            'design': base_cv.get('design', {'theme': 'classic'}),
            'locale': base_cv.get('locale', {'language': 'english'}),
            'settings': base_cv.get('settings', {
                'current_date': '2025-12-22',
                'render_command': {
                    'design': {},
                    'locale': {},
                    'pdf_path': 'rendercv_output/NAME_IN_SNAKE_CASE_CV.pdf',
                    'dont_generate_markdown': False,
                    'dont_generate_html': False,
                    'dont_generate_typst': False,
                    'dont_generate_pdf': False,
                    'dont_generate_png': False
                },
                'bold_keywords': []
            })
        }

        # TODO: Add validation to ensure CV content accuracy against verified data

        return merged_cv

    async def _customize_cv_with_ai(self, base_cv: Dict[str, Any], job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to intelligently customize CV content based on job requirements and personal context"""
        try:
            # Prepare context data for the AI
            job_description = job_info.get('description', '')
            job_title = job_info.get('title', '')
            company = job_info.get('company', '')

            # Extract personal context from RAG
            personal_info = {}
            if rag_context.get('personal_info') and len(rag_context['personal_info']) > 0:
                # Get the first personal info record
                personal_info_record = rag_context['personal_info'][0]
                if 'content' in personal_info_record:
                    personal_info = personal_info_record['content']
            skills = rag_context.get('skills', [])
            experiences = rag_context.get('experiences', [])
            projects = rag_context.get('projects', [])
            education = rag_context.get('education', [])

            # Format skills properly (extract names from dictionaries if needed)
            formatted_skills = []
            if skills:
                for skill in skills[:10]:  # Limit for prompt
                    if isinstance(skill, dict):
                        if 'name' in skill:
                            formatted_skills.append(skill['name'])
                        elif 'content' in skill:
                            formatted_skills.append(skill['content'])
                        else:
                            formatted_skills.append(str(skill))
                    else:
                        formatted_skills.append(skill)

            # Format the prompt with actual data
            prompt = CV_CUSTOMIZATION_PROMPT.format(
                job_title=job_title,
                company=company,
                job_description=job_description[:2000] + "..." if len(job_description) > 2000 else job_description,
                skills=', '.join(formatted_skills) if formatted_skills else 'None provided',
                experience=json.dumps(experiences[:3], indent=2) if experiences else 'None provided',
                projects=json.dumps(projects[:2], indent=2) if projects else 'None provided',
                education=json.dumps(education, indent=2) if education else 'None provided'
            )

            if self.verbose:
                self.console.print("🤖 Customizing CV with AI based on job requirements")

            response = await self.chat_openai.ainvoke(prompt)
            customized_json = response.content.strip()

            # Remove markdown code blocks if present
            if customized_json.startswith('```json'):
                customized_json = customized_json[7:]
            if customized_json.startswith('```'):
                customized_json = customized_json[3:]
            if customized_json.endswith('```'):
                customized_json = customized_json[:-3]

            # Parse the customized JSON back to dict
            customized_cv_dict = json.loads(customized_json.strip())
            return customized_cv_dict

        except Exception as e:
            raise Exception(f"AI customization failed: {str(e)}")

    def _validate_cv_dict(self, cv_dict: Dict[str, Any]) -> None:
        """Validate critical CV requirements"""
        # 1. Name must not be none
        if cv_dict.get('name') is None:
            raise Exception("CV name field cannot be null")

        # 2. All start_date and end_date must not be none
        if 'sections' in cv_dict and isinstance(cv_dict['sections'], dict):
            # Check education dates
            if 'education' in cv_dict['sections'] and isinstance(cv_dict['sections']['education'], list):
                for edu in cv_dict['sections']['education']:
                    if isinstance(edu, dict):
                        if edu.get('start_date') is None:
                            raise Exception("Education start_date cannot be null")
                        if edu.get('end_date') is None:
                            raise Exception("Education end_date cannot be null")

            # Check experience dates
            if 'experience' in cv_dict['sections'] and isinstance(cv_dict['sections']['experience'], list):
                for exp in cv_dict['sections']['experience']:
                    if isinstance(exp, dict):
                        if exp.get('start_date') is None:
                            raise Exception("Experience start_date cannot be null")
                        if exp.get('end_date') is None:
                            raise Exception("Experience end_date cannot be null")

            # Check project dates (if present)
            if 'projects' in cv_dict['sections'] and isinstance(cv_dict['sections']['projects'], list):
                for proj in cv_dict['sections']['projects']:
                    if isinstance(proj, dict):
                        if 'start_date' in proj and proj.get('start_date') is None:
                            raise Exception("Project start_date cannot be null if present")
                        if 'end_date' in proj and proj.get('end_date') is None:
                            raise Exception("Project end_date cannot be null if present")

        # 3. If social network is not none, username must not be none
        if 'social_networks' in cv_dict and isinstance(cv_dict['social_networks'], list):
            for network in cv_dict['social_networks']:
                if isinstance(network, dict):
                    network_val = network.get('network')
                    username_val = network.get('username')
                    if network_val is not None and username_val is None:
                        raise Exception("Social network with network specified must have non-null username")
                    if username_val is not None and network_val is None:
                        raise Exception("Social network with username specified must have non-null network")


    async def _save_cv_yaml(self, cv_data: Dict[str, Any], job_info: Dict[str, Any]) -> pathlib.Path:
        """Save customized CV as YAML file"""
        # Clean up any problematic sections that AI might have added
        if 'locale' in cv_data and isinstance(cv_data['locale'], dict):
            if 'language' in cv_data['locale'] and cv_data['locale']['language'] == 'en':
                cv_data['locale']['language'] = 'english'
            # If it still has issues, remove the locale section entirely
            if cv_data['locale'].get('language') not in ['english', 'danish', 'french', 'german', 'hindi', 'indonesian', 'italian', 'japanese', 'korean', 'mandarin_chineese', 'portuguese', 'russian', 'spanish', 'turkish']:
                del cv_data['locale']

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

