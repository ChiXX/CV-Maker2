#!/usr/bin/env python3
"""
CV Agent - Automated CV and Cover Letter Generation System

This agent system:
1. Takes job URLs as input
2. Extracts job descriptions from web pages
3. Uses RAG database to generate tailored CVs and cover letters
4. Creates organized directory structure with generated files
"""

import asyncio
import pathlib
import sys
from typing import Annotated

import typer
from rich import print
from rich.console import Console

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system environment variables

from agent import CVAgent
from config import Config, CVCLConfig, save_user_personal_info

console = Console()
app = typer.Typer(
    name="cv-agent",
    help="Automated CV and Cover Letter Generation System",
    rich_markup_mode="rich",
)


@app.command()
def generate(
    name: Annotated[str, typer.Argument(help="Your name/identifier for loading user data")],
    linkedin_url: Annotated[str, typer.Argument(help="LinkedIn job posting URL")],
    output_dir: Annotated[
        pathlib.Path | None,
        typer.Option("--output", "-o", help="Output directory for generated files")
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output")
    ] = False,
):
    """
    Generate a tailored CV and cover letter for a job posting.

    The agent will:
    1. Load your personal data from the user folder
    2. Extract the job description from the LinkedIn URL
    3. Use your personal RAG database to customize content
    4. Validate content to ensure honesty and accuracy
    5. Generate PDF versions of CV and cover letter
    6. Create organized directory structure
    """
    try:
        # Load configurations
        config = Config(name)
        cvcl_config = CVCLConfig()

        # Set user-specific paths
        user_paths = config.get_user_paths(name)
        config.rag["vector_store_path"] = user_paths["vector_store"]

        # Override output directory if specified
        if output_dir:
            config.output_dir = output_dir

        console.print(f"[bold blue]🚀 Starting CV Agent for {name}[/bold blue]")
        console.print(f"[dim]job_url: {linkedin_url}[/dim]")

        # Initialize and run agent
        agent = CVAgent(config, cvcl_config, verbose=verbose)

        # Run the generation process
        asyncio.run(agent.process_job(linkedin_url))

        console.print("[bold green]✅ CV and Cover Letter generation completed![/bold green]")

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


@app.command()
def setup_rag(
    name: Annotated[str, typer.Argument(help="Your name/identifier for the user profile")],
    personal_info_file: Annotated[
        pathlib.Path | None,
        typer.Option("--personal-info", help="Path to personal information file")
    ] = None,
    career_data_dir: Annotated[
        pathlib.Path | None,
        typer.Option("--career-data", help="Directory containing career data files")
    ] = None,
    code_samples_dir: Annotated[
        pathlib.Path | None,
        typer.Option("--code-samples", help="Directory containing code samples")
    ] = None,
    config_file: Annotated[
        pathlib.Path | None,
        typer.Option("--config", "-c", help="Path to configuration file")
    ] = None,
):
    """
    Initialize a user profile and set up the personal RAG database.

    This command creates a user folder structure and builds your personal knowledge base
    that the agent uses to generate tailored CVs and cover letters.
    """
    try:
        config = Config(name)

        # Load global CV/CL configuration
        cvcl_config = CVCLConfig()

        # Get user-specific paths
        user_paths = config.get_user_paths(name)

        console.print(f"[bold blue]🔧 Initializing user profile for {name}...[/bold blue]")

        # Create user directory structure
        user_paths["user_dir"].mkdir(parents=True, exist_ok=True)
        user_paths["career_data"].mkdir(exist_ok=True)
        user_paths["code_samples"].mkdir(exist_ok=True)

        # Create template personal info file if it doesn't exist
        if not user_paths["personal_info"].exists():
            template_personal_info = {
                "name": name,
                "email": "your.email@example.com",
                "phone": "+1-234-567-8900",
                "location": {
                    "city": "Your City",
                    "country": "Your Country"
                },
                "linkedin": f"https://linkedin.com/in/your-profile",
                "website": "https://yourwebsite.com",
                "summary": "Brief professional summary highlighting your key strengths and experience.",
                "skills": ["Skill 1", "Skill 2", "Skill 3"],
                "experiences": [
                    {
                        "company": "Previous Company",
                        "position": "Your Position",
                        "start_date": "2020-01",
                        "end_date": "2023-12",
                        "description": "Description of your role and achievements.",
                        "technologies": ["Tech 1", "Tech 2"]
                    }
                ],
                "education": [
                    {
                        "institution": "University Name",
                        "degree": "Bachelor of Science",
                        "field": "Computer Science",
                        "graduation_year": 2023
                    }
                ],
                "projects": [
                    {
                        "name": "Project Name",
                        "description": "Description of the project and your contributions.",
                        "technologies": ["Tech 1", "Tech 2"],
                        "url": "https://github.com/yourusername/project"
                    }
                ]
            }
            import json
            with open(user_paths["personal_info"], 'w', encoding='utf-8') as f:
                json.dump(template_personal_info, f, indent=2, ensure_ascii=False)

        # Save user config (only user-specific settings, no CV/CL config)
        config.rag.vector_store_path = user_paths["vector_store"]
        config.save(user_paths["config_file"])

        console.print(f"[green]✓ Created user directory: {user_paths['user_dir']}[/green]")
        console.print(f"[green]✓ Created config file: {user_paths['config_file']}[/green]")
        console.print(f"[green]✓ Created personal info template: {user_paths['personal_info']}[/green]")
        console.print(f"[green]✓ Using global CV/CL config: {cvcl_config.cv.base_cv_file}[/green]")

        # Set up RAG database with the created paths
        agent = CVAgent(config, cvcl_config)
        agent.setup_rag_database(
            personal_info_file=personal_info_file or user_paths["personal_info"],
            career_data_dir=career_data_dir or user_paths["career_data"],
            code_samples_dir=code_samples_dir or user_paths["code_samples"],
        )

        console.print("[bold green]✅ User profile and RAG database setup completed![/bold green]")
        console.print(f"[dim]User folder: {user_paths['user_dir']}[/dim]")
        console.print(f"[dim]Edit {user_paths['personal_info']} to add your personal information[/dim]")

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def init_config(
    output_file: Annotated[
        pathlib.Path,
        typer.Argument(help="Path where config file should be created")
    ] = pathlib.Path("cv-agent-config.yaml"),
):
    """
    Generate a default configuration file for the CV agent.
    """
    try:
        # Create a template personal info file
        from config import get_user_paths
        template_data = {
            "name": "Your Full Name",
            "email": "your.email@example.com",
            "phone": "+1-234-567-8900",
            "location": {
                "city": "Your City",
                "country": "Your Country"
            },
            "linkedin": "https://linkedin.com/in/yourprofile",
            "website": "https://yourwebsite.com",
            "summary": "Brief professional summary highlighting your key strengths and experience.",
            "skills": ["Skill 1", "Skill 2", "Skill 3"],
            "experiences": [
                {
                    "company": "Previous Company",
                    "position": "Your Position",
                    "start_date": "2020-01",
                    "end_date": "2023-12",
                    "description": "Description of your role and achievements.",
                    "technologies": ["Tech 1", "Tech 2"]
                }
            ],
            "education": [
                {
                    "institution": "University Name",
                    "degree": "Bachelor of Science",
                    "field": "Computer Science",
                    "graduation_year": 2023
                }
            ],
            "projects": [
                {
                    "name": "Project Name",
                    "description": "Description of the project and your contributions.",
                    "technologies": ["Tech 1", "Tech 2"],
                    "url": "https://github.com/yourusername/project"
                }
            ]
        }
        save_user_personal_info("template_user", template_data)
        user_paths = get_user_paths("template_user")
        console.print(f"[bold green]✅ User config template created:[/bold green] {user_paths['personal_info']}")
        console.print("[dim]Edit this file with your personal information before running the agent.[/dim]")

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def graph(
    config_file: Annotated[
        pathlib.Path | None,
        typer.Option("--config", "-c", help="Path to configuration file")
    ] = None,
    output_file: Annotated[
        pathlib.Path | None,
        typer.Option("--output", "-o", help="Output file for graph (PNG or DOT). PNG requires system graphviz, DOT works with Python package only")
    ] = None,
):
    """
    Display or save the agent graph visualization.

    Shows the LangGraph workflow structure with all nodes and edges.
    Use --output to save as PNG image (requires system graphviz) or DOT file (Python package only).
    """
    try:
        # Load configuration
        config = Config("default_user")  # Use default user for graph visualization

        console.print("[bold blue]📊 Generating agent graph visualization...[/bold blue]")

        # Initialize the LangGraph agent to build the graph
        from langgraph_agent import LangGraphAgent
        agent = LangGraphAgent(config, verbose=False)

        if output_file:
            # Save as image
            agent.save_graph_image(str(output_file))
        else:
            # Display text visualization
            graph_viz = agent.get_graph_visualization()
            console.print(graph_viz)

    except ImportError as e:
        console.print(f"[bold red]❌ Missing dependency:[/bold red] {str(e)}")
        console.print("Install graphviz for image output: uv sync --extra graphviz")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
