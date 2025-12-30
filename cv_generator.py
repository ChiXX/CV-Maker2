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

CV_CUSTOMIZATION_PROMPT = """You are an expert CV customization consultant. Your task is to create a complete, properly formatted CV in RenderCV YAML format based on a job opportunity and personal information.

JOB OPPORTUNITY:
- Title: {job_title}
- Company: {company}
- Description: {job_description}

PERSONAL CONTEXT (verified information only):
Skills: {skills}
Experience: {experience}
Projects: {projects}
Education: {education}

REQUIRED OUTPUT FORMAT:
You must return a complete YAML structure that follows RenderCV v2.x format EXACTLY. The output should be a valid cv section that can be directly used with RenderCV.

CRITICAL REQUIREMENTS:
- Return ONLY the cv section, not the full YAML with design/locale
- Personal info: name, headline, email, phone, website, linkedin, location
- Use sections object containing: experience, education, projects, skills
- Each section must be an array of properly structured objects

EXACT FIELD REQUIREMENTS:

1. **cv structure**:
   cv:
     name: "Full Name"
     headline: "Professional headline"
     email: "email@domain.com"
     phone: "+1234567890"
     website: "https://website.com"
     linkedin: "https://linkedin.com/in/profile"
     location: "City, Country"
     sections:
       experience: [...]
       education: [...]
       projects: [...]
       skills: [...]

2. **experience entries** (array of objects):
   - company: "Company Name" (string)
   - position: "Job Title" (string)
   - start_date: "YYYY-MM" (string)
   - end_date: "YYYY-MM" or "present" (string)
   - location: "City, Country" (string)
   - highlights: ["Bullet point 1", "Bullet point 2"] (array of strings)

3. **education entries** (array of objects):
   - institution: "University Name" (string)
   - area: "Field of Study" (string)
   - degree: "Degree Name" (string)
   - start_date: "YYYY-MM" (string)
   - end_date: "YYYY-MM" (string)
   - location: "City, Country" (string)
   - highlights: ["Achievement 1", "Achievement 2"] (array of strings)

4. **projects entries** (array of objects):
   - name: "Project Name" (string)
   - start_date: "YYYY-MM" (string)
   - end_date: "YYYY-MM" or "present" (string)
   - highlights: ["Description 1", "Description 2"] (array of strings)

5. **skills entries** (array of objects):
   - label: "Category Name" (string, e.g., "Programming Languages")
   - details: "Skill1, Skill2, Skill3" (string, comma-separated)

INSTRUCTIONS:
1. **Headline**: Create a compelling 1-2 sentence headline highlighting relevant experience for this job.

2. **Experience Section** (REQUIRED):
   - Create 2-4 experience entries from provided personal context
   - Each must have ALL required fields with realistic content
   - Focus on achievements matching the job description
   - Use YYYY-MM format for dates

3. **Education Section** (REQUIRED):
   - Create 1-2 education entries from provided context
   - Include relevant achievements and coursework

4. **Projects Section** (REQUIRED):
   - Create 2-3 project entries demonstrating relevant skills
   - Show technical achievements and technologies used

5. **Skills Section** (REQUIRED):
   - Create 3-5 skill categories from provided skills
   - Group logically (Languages, Frameworks, Tools, etc.)
   - Prioritize skills mentioned in job description

IMPORTANT RULES:
- Use EXACT field names and structure as specified
- Dates must be in YYYY-MM format
- Empty arrays [] are allowed but all required fields must be present
- NEVER fabricate information beyond what's provided
- Return ONLY valid YAML cv section (no design/locale/settings)
- Ensure proper YAML indentation and formatting

EXAMPLE OUTPUT STRUCTURE:
cv:
  name: "John Doe"
  headline: "Senior Full-Stack Engineer with 5+ years experience"
  email: "john@email.com"
  phone: "+1234567890"
  website: "https://johndoe.com"
  linkedin: "https://linkedin.com/in/johndoe"
  location: "San Francisco, CA"
  sections:
    experience:
      - company: "Tech Corp"
        position: "Senior Developer"
        start_date: "2020-01"
        end_date: "present"
        location: "San Francisco, CA"
        highlights:
          - "Led development of scalable web applications"
          - "Mentored junior developers"
    education:
      - institution: "University of California"
        area: "Computer Science"
        degree: "Bachelor of Science"
        start_date: "2016-09"
        end_date: "2020-05"
        location: "Berkeley, CA"
        highlights:
          - "GPA: 3.8/4.0"
    projects:
      - name: "E-commerce Platform"
        start_date: "2022-03"
        end_date: "2022-08"
        highlights:
          - "Built with React and Node.js"
          - "Handled 10k+ daily users"
    skills:
      - label: "Programming Languages"
        details: "JavaScript, Python, TypeScript"
      - label: "Frameworks"
        details: "React, Node.js, Express"""


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
            model=llm_config.get('model', 'mistralai/mistral-small-3.1-24b-instruct:free'),
            temperature=llm_config.get('temperature', 0.1),
            max_tokens=llm_config.get('max_tokens', 4000)
        )

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
        """Load the base CV template from the templates directory"""
        # Get the directory where this script is located, then go up to project root
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
        # Use AI to intelligently customize the entire CV at once
        customized_cv = await self._customize_cv_with_ai(base_cv, job_info, rag_context)

        # TODO: Add validation to ensure CV content accuracy against verified data

        return customized_cv

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

            # Convert base CV to YAML string for AI processing
            base_cv_yaml = yaml.dump(base_cv, default_flow_style=False, allow_unicode=True)

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
                experience=yaml.dump(experiences[:3], default_flow_style=False) if experiences else 'None provided',
                projects=yaml.dump(projects[:2], default_flow_style=False) if projects else 'None provided',
                education=yaml.dump(education, default_flow_style=False) if education else 'None provided',
                base_cv_yaml=base_cv_yaml
            )

            if self.verbose:
                self.console.print("🤖 Customizing CV with AI based on job requirements")

            response = await self.chat_openai.ainvoke(prompt)
            customized_yaml = response.content.strip()

            # Remove markdown code blocks if present
            if customized_yaml.startswith('```yaml'):
                customized_yaml = customized_yaml[7:]
            if customized_yaml.startswith('```'):
                customized_yaml = customized_yaml[3:]
            if customized_yaml.endswith('```'):
                customized_yaml = customized_yaml[:-3]


            # Parse the customized YAML back to dict
            ai_response = yaml.safe_load(customized_yaml.strip())

            # The AI should only return the cv section, so combine it with base template
            customized_cv = base_cv.copy()
            if 'cv' in ai_response:
                customized_cv['cv'] = ai_response['cv']
            else:
                # AI returned just the sections/personal info, merge into cv
                customized_cv['cv'].update(ai_response)

            # Ensure sections exist
            if 'sections' not in customized_cv['cv']:
                customized_cv['cv']['sections'] = {}

            # Override personal information with data from personal_info if available
            if personal_info:
                customized_cv['cv']['name'] = personal_info.get('name', customized_cv['cv'].get('name', 'Your Name'))
                customized_cv['cv']['email'] = personal_info.get('email', customized_cv['cv'].get('email', ''))
                customized_cv['cv']['phone'] = personal_info.get('phone', customized_cv['cv'].get('phone', ''))
                customized_cv['cv']['website'] = personal_info.get('website', customized_cv['cv'].get('website', ''))
                # Only set location if it has a meaningful value
                location = personal_info.get('location', customized_cv['cv'].get('location', ''))
                if location and location.strip():
                    customized_cv['cv']['location'] = location
                customized_cv['cv']['linkedin'] = personal_info.get('linkedin', customized_cv['cv'].get('linkedin', ''))

            if self.verbose:
                self.console.print("✅ CV customization completed")

            return customized_cv

        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]AI customization failed, creating basic CV from available data: {str(e)}[/yellow]")
            return await self._create_basic_cv_from_rag(base_cv, job_info, rag_context)





    async def _create_basic_cv_from_rag(self, base_cv: Dict[str, Any], job_info: Dict[str, Any], rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a basic CV from available RAG data when AI is not available"""
        # Start with the base CV
        cv = base_cv.copy()

        # Debug: print RAG context structure
        if self.verbose:
            self.console.print(f"[dim]RAG context keys: {list(rag_context.keys())}[/dim]")
            if 'personal_info' in rag_context and rag_context['personal_info']:
                self.console.print(f"[dim]Personal info records: {len(rag_context['personal_info'])}[/dim]")
            if 'experiences' in rag_context:
                self.console.print(f"[dim]Experience records: {len(rag_context['experiences'])}[/dim]")
            if 'skills' in rag_context:
                self.console.print(f"[dim]Skills records: {len(rag_context['skills'])}[/dim]")

        # Extract personal info
        personal_info = {}
        if rag_context.get('personal_info') and len(rag_context['personal_info']) > 0:
            personal_info_record = rag_context['personal_info'][0]
            if 'content' in personal_info_record:
                personal_info = personal_info_record['content']
                if self.verbose:
                    self.console.print(f"[dim]Personal info keys: {list(personal_info.keys())}[/dim]")

        # Set personal information
        if personal_info:
            cv['cv']['name'] = personal_info.get('name', 'Your Name')
            cv['cv']['email'] = personal_info.get('email', '')
            cv['cv']['phone'] = personal_info.get('phone', '')

            # Handle location (could be string or dict) - only set if meaningful
            location = personal_info.get('location', '')
            location_str = ''
            if isinstance(location, dict):
                city = location.get('city', '')
                country = location.get('country', '')
                location_str = f"{city}, {country}".strip(', ')
            elif isinstance(location, str):
                location_str = location
            else:
                location_str = str(location)

            # Only set location if it has content
            if location_str and location_str.strip():
                cv['cv']['location'] = location_str

            cv['cv']['website'] = personal_info.get('website', '')
            cv['cv']['linkedin'] = personal_info.get('linkedin', '')

            # Create headline from summary if available
            if personal_info.get('summary'):
                cv['cv']['headline'] = personal_info['summary'][:200] + "..." if len(personal_info['summary']) > 200 else personal_info['summary']

        # Initialize sections
        cv['cv']['sections'] = {}

        # Add experiences - try personal_info first, then RAG context
        experiences_data = []
        if personal_info.get('experiences'):
            experiences_data = personal_info['experiences']
            if self.verbose:
                self.console.print(f"[dim]Using experiences from personal_info: {len(experiences_data)}[/dim]")
        elif rag_context.get('experiences'):
            experiences_data = rag_context['experiences']
            if self.verbose:
                self.console.print(f"[dim]Using experiences from RAG context (plural): {len(experiences_data)}[/dim]")
        elif rag_context.get('experience'):  # fallback singular form
            experiences_data = rag_context['experience']
            if self.verbose:
                self.console.print(f"[dim]Using experiences from RAG context (singular): {len(experiences_data)}[/dim]")

        if experiences_data:
            cv['cv']['sections']['experience'] = []
            for exp in experiences_data[:3]:  # Limit to 3 most recent
                # Handle different data formats
                if isinstance(exp, dict):
                    if 'content' in exp and isinstance(exp['content'], str):
                        # RAG context format - content is JSON string
                        try:
                            exp_data = json.loads(exp['content'])
                        except:
                            exp_data = exp
                    else:
                        # Direct experience data
                        exp_data = exp
                else:
                    continue

                # Ensure exp_data is a dict
                if not isinstance(exp_data, dict):
                    continue

                experience_entry = {
                    'company': exp_data.get('company', ''),
                    'position': exp_data.get('position', ''),
                    'start_date': exp_data.get('start_date', ''),
                    'end_date': exp_data.get('end_date', 'present'),
                    'location': exp_data.get('location', ''),
                    'highlights': []
                }

                # Add description as highlights
                if exp_data.get('description'):
                    # Split description into bullet points
                    highlights = exp_data['description'].split('. ')
                    experience_entry['highlights'] = [h.strip() + '.' for h in highlights if h.strip()]

                cv['cv']['sections']['experience'].append(experience_entry)

        # Add education - try personal_info first, then RAG context
        education_data = []
        if personal_info.get('education'):
            education_data = personal_info['education']
        elif rag_context.get('education'):
            education_data = rag_context['education']

        if education_data:
            education_entries = []
            for edu in education_data[:2]:  # Limit to 2
                # Handle different data formats
                if isinstance(edu, dict):
                    if 'content' in edu and isinstance(edu['content'], str):
                        # RAG context format - content is JSON string
                        try:
                            edu_data = json.loads(edu['content'])
                        except:
                            edu_data = edu
                    else:
                        # Direct education data
                        edu_data = edu
                else:
                    continue

                # Ensure edu_data is a dict
                if not isinstance(edu_data, dict):
                    continue

                # Calculate dates properly
                grad_year = edu_data.get('graduation_year')
                if grad_year and isinstance(grad_year, int):
                    start_year = max(1900, grad_year - 4)  # Ensure reasonable year
                    start_date = f"{start_year}-09"  # Assume September start
                    end_date = f"{grad_year}-06"  # Assume June graduation
                else:
                    start_date = edu_data.get('start_date', '')
                    end_date = edu_data.get('end_date', '')

                education_entry = {
                    'institution': edu_data.get('institution', ''),
                    'area': edu_data.get('field', edu_data.get('area', '')),
                    'degree': edu_data.get('degree', ''),
                    'start_date': start_date,
                    'end_date': end_date,
                    'location': edu_data.get('location', ''),
                    'highlights': []
                }

                if edu_data.get('description'):
                    highlights = edu_data['description'].split('. ')
                    education_entry['highlights'] = [h.strip() + '.' for h in highlights if h.strip()]

                # Only add if we have meaningful data
                if education_entry['institution'] or education_entry['degree']:
                    education_entries.append(education_entry)

            if education_entries:
                cv['cv']['sections']['education'] = education_entries

        # Add skills - try personal_info first, then RAG context
        skills_data = []
        if personal_info.get('skills'):
            skills_data = [{'name': skill, 'source': 'personal_info'} for skill in personal_info['skills']]
        elif rag_context.get('skills'):
            skills_data = rag_context['skills']

        if skills_data:
            cv['cv']['sections']['skills'] = []
            # Group skills by category
            skill_groups = {}
            for skill in skills_data[:15]:  # Limit total skills
                # Handle different skill formats
                if isinstance(skill, dict):
                    if 'name' in skill:
                        skill_name = skill['name']
                    elif 'content' in skill:
                        skill_name = skill['content']
                    else:
                        skill_name = str(skill)
                else:
                    skill_name = skill

                # Ensure skill_name is a string
                if not isinstance(skill_name, str):
                    skill_name = str(skill_name)

                # Simple categorization
                if any(tech in skill_name.lower() for tech in ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 'go', 'rust']):
                    category = 'Programming Languages'
                elif any(tech in skill_name.lower() for tech in ['react', 'angular', 'vue', 'jquery', 'html', 'css', 'sass', 'bootstrap', 'tailwind']):
                    category = 'Frontend Frameworks'
                elif any(tech in skill_name.lower() for tech in ['node', 'express', 'django', 'flask', 'spring', 'laravel', 'rails']):
                    category = 'Backend Frameworks'
                elif any(tech in skill_name.lower() for tech in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch']):
                    category = 'Databases'
                elif any(tech in skill_name.lower() for tech in ['docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform']):
                    category = 'DevOps & Cloud'
                else:
                    category = 'Other Skills'

                if category not in skill_groups:
                    skill_groups[category] = []
                skill_groups[category].append(skill_name)

            # Convert to CV format
            for category, skills_list in skill_groups.items():
                cv['cv']['sections']['skills'].append({
                    'label': category,
                    'details': ', '.join(skills_list)
                })

        # Add projects - try personal_info first, then RAG context
        projects_data = []
        if personal_info.get('projects'):
            projects_data = personal_info['projects']
        elif rag_context.get('projects'):
            projects_data = rag_context['projects']

        if projects_data:
            project_entries = []
            for proj in projects_data[:3]:  # Limit to 3
                # Handle different data formats
                if isinstance(proj, dict):
                    if 'content' in proj and isinstance(proj['content'], str):
                        # RAG context format - content is JSON string
                        try:
                            proj_data = json.loads(proj['content'])
                        except:
                            proj_data = proj
                    else:
                        # Direct project data
                        proj_data = proj
                else:
                    continue

                # Ensure proj_data is a dict
                if not isinstance(proj_data, dict):
                    continue

                project_entry = {
                    'name': proj_data.get('name', ''),
                    'highlights': []
                }

                # Only add dates if they exist and are valid
                start_date = proj_data.get('start_date', '').strip()
                end_date = proj_data.get('end_date', 'present').strip()

                if start_date:
                    project_entry['start_date'] = start_date
                if end_date:
                    project_entry['end_date'] = end_date

                if proj_data.get('description'):
                    highlights = proj_data['description'].split('. ')
                    project_entry['highlights'] = [h.strip() + '.' for h in highlights if h.strip()]

                # Only add if we have meaningful data
                if project_entry['name']:
                    project_entries.append(project_entry)

            if project_entries:
                cv['cv']['sections']['projects'] = project_entries

        return cv


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

