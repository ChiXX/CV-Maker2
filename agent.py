"""Main CV Agent class that orchestrates the CV generation process"""

import asyncio
import datetime
import pathlib
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config import Config, CVCLConfig
from job_extractor import JobExtractor
from rag_system import RAGSystem
from cv_generator import CVGenerator
from cover_letter_generator import CoverLetterGenerator
from langgraph_agent import LangGraphAgent
from utils import sanitize_filename


class CVAgent:
    """Main agent class for automated CV and cover letter generation"""

    def __init__(self, config: Config, cvcl_config: Optional[CVCLConfig] = None, verbose: bool = False):
        self.config = config
        self.cvcl_config = cvcl_config or CVCLConfig.load()
        self.verbose = verbose
        self.console = Console()

        # Initialize LangGraph agent
        self.langgraph_agent = LangGraphAgent(config, cvcl_config, verbose=verbose)

    async def process_job(self, job_url: str) -> None:
        """Main processing pipeline for a job URL using LangGraph"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:

            # Use LangGraph agent for processing
            task = progress.add_task("🤖 Running CV Agent workflow...", total=1)
            result = await self.langgraph_agent.process_job(job_url)
            progress.update(task, completed=1)

            # Check for errors
            if result.get("status") in ["error", "completed_with_errors"]:
                errors = result.get("errors", [])
                for error in errors:
                    self.console.print(f"[red]⚠️  {error}[/red]")

            # Display results
            if result.get("status") == "completed" or result.get("output_dir"):
                output_dir = result.get("output_dir")
                if output_dir:
                    self.console.print(f"\n[bold green]🎉 Application package created![/bold green]")
                    self.console.print(f"📂 Location: [blue]{output_dir}[/blue]")
                    self.console.print("📋 Contents:")
                    self.console.print("   ├── summary.txt (job details)")
                    self.console.print("   ├── CV.pdf")
                    self.console.print("   └── cover_letter.pdf")
                else:
                    self.console.print("[yellow]⚠️  Process completed but output directory not created[/yellow]")
            else:
                self.console.print("[red]❌ Process failed to complete successfully[/red]")
    def setup_rag_database(
        self,
        personal_info_file: Optional[pathlib.Path] = None,
        career_data_dir: Optional[pathlib.Path] = None,
        code_samples_dir: Optional[pathlib.Path] = None,
    ) -> None:
        """Set up and populate the personal RAG database"""
        self.console.print("[bold blue]🔧 Setting up personal RAG database...[/bold blue]")

        # Update config with provided paths
        if personal_info_file:
            self.config.rag.personal_info_file = personal_info_file
        if career_data_dir:
            self.config.rag.career_data_dir = career_data_dir
        if code_samples_dir:
            self.config.rag.code_samples_dir = code_samples_dir

        # Initialize RAG system via LangGraph agent
        asyncio.run(self.langgraph_agent.setup_rag_database())

        self.console.print("[bold green]✅ RAG database setup completed![/bold green]")
        self.console.print("\n[dim]Database structure created. To populate with your data:[/dim]")
        if self.config.rag.personal_info_file and self.config.rag.personal_info_file.exists():
            self.console.print(f"   ✅ Personal info template: {self.config.rag.personal_info_file} [green](edit this file)[/green]")
        if self.config.rag.career_data_dir:
            self.console.print(f"   📁 Career data: {self.config.rag.career_data_dir} [yellow](add resume, certificates, etc.)[/yellow]")
        if self.config.rag.code_samples_dir:
            self.console.print(f"   📁 Code samples: {self.config.rag.code_samples_dir} [yellow](add code files, projects)[/yellow]")

    def _create_output_directory(self, job_info: Dict[str, Any]) -> pathlib.Path:
        """Create organized output directory with date_company_jobtitle format"""
        today = datetime.date.today().isoformat()

        # Extract and sanitize company name
        company = sanitize_filename(job_info.get('company', 'UnknownCompany'))

        # Extract and sanitize job title
        title = sanitize_filename(job_info.get('title', 'UnknownPosition'))

        # Create directory name
        dir_name = f"{today}_{company}_{title}"
        output_dir = self.cvcl_config.output_dir / dir_name

        # Create directory
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    async def _save_files(
        self,
        output_dir: pathlib.Path,
        job_info: Dict[str, Any],
        cv_file: pathlib.Path,
        cl_file: pathlib.Path,
    ) -> None:
        """Save all generated files to the output directory"""
        # Copy CV and cover letter PDFs
        import shutil

        cv_dest = output_dir / "CV.pdf"
        cl_dest = output_dir / "cover_letter.pdf"

        shutil.copy2(cv_file, cv_dest)
        shutil.copy2(cl_file, cl_dest)

        # Create summary.txt
        summary_content = f"""Job Application Summary
========================

Job URL: {job_info.get('url', 'N/A')}
Company: {job_info.get('company', 'N/A')}
Position: {job_info.get('title', 'N/A')}
Location: {job_info.get('location', 'N/A')}

Job Description:
{job_info.get('description', 'N/A')}

Generated on: {datetime.datetime.now().isoformat()}
"""

        summary_file = output_dir / "summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)
