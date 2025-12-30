#!/usr/bin/env python3
"""
Quick setup script for CV Agent
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
from typing import Optional

from .config import Config


def main():
    parser = argparse.ArgumentParser(description="CV Agent Setup Script")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick setup with minimal configuration"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full setup with example data structure"
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path("./cv-agent-setup"),
        help="Output directory for setup files"
    )

    args = parser.parse_args()

    if args.quick:
        quick_setup(args.output_dir)
    elif args.full:
        full_setup(args.output_dir)
    else:
        print("CV Agent Setup Script")
        print("=" * 40)
        print()
        print("Choose a setup option:")
        print("1. Quick setup (minimal configuration)")
        print("2. Full setup (with example data structure)")
        print()
        choice = input("Enter your choice (1 or 2): ").strip()

        if choice == "1":
            quick_setup(args.output_dir)
        elif choice == "2":
            full_setup(args.output_dir)
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)


def quick_setup(output_dir: pathlib.Path):
    """Quick setup with minimal configuration"""
    print("🚀 Performing quick setup...")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create basic config
    config = Config()
    config_file = output_dir / "cv-agent-config.yaml"
    config.save(config_file)

    print(f"✅ Created configuration file: {config_file}")

    # Create basic directory structure
    dirs = ["career_data", "code_samples", "generated_applications"]
    for dir_name in dirs:
        (output_dir / dir_name).mkdir(exist_ok=True)

    # Create example personal info file
    personal_info = output_dir / "career_data" / "personal_info.json"
    create_example_personal_info(personal_info)

    print(f"✅ Created basic directory structure in: {output_dir}")
    print(f"✅ Created example personal info file: {personal_info}")
    print()
    print("Next steps:")
    print("1. Edit the configuration file with your settings")
    print("2. Update the personal info file with your details")
    print("3. Add your career documents to the career_data/ directory")
    print("4. Run: cv-agent setup-rag --config cv-agent-config.yaml")
    print("5. Try: cv-agent generate 'job_url'")
    print()
    print("📖 For detailed setup instructions, see: RAG_SETUP_GUIDE.md")


def full_setup(output_dir: pathlib.Path):
    """Full setup with example data structure"""
    print("🔧 Performing full setup with example structure...")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create configuration
    config = Config()
    config.rag.personal_info_file = output_dir / "personal_info.json"
    config.rag.career_data_dir = output_dir / "career_data"
    config.rag.code_samples_dir = output_dir / "code_samples"
    config.output_dir = output_dir / "generated_applications"

    config_file = output_dir / "cv-agent-config.yaml"
    config.save(config_file)

    print(f"✅ Created configuration file: {config_file}")

    # Create comprehensive directory structure
    create_full_directory_structure(output_dir)

    # Create example files
    create_example_files(output_dir)

    print(f"✅ Created full directory structure in: {output_dir}")
    print()
    print("📂 Created directories:")
    print("  ├── career_data/          # Your career documents")
    print("  ├── code_samples/         # Your code examples")
    print("  ├── generated_applications/  # Generated CVs and cover letters")
    print("  ├── personal_info.json    # Your personal information")
    print("  └── cv-agent-config.yaml  # Configuration file")
    print()
    print("Next steps:")
    print("1. Edit personal_info.json with your actual information")
    print("2. Replace example files in career_data/ with your real documents")
    print("3. Add your code samples to code_samples/")
    print("4. Run: cv-agent setup-rag --config cv-agent-config.yaml")
    print("5. Try: cv-agent generate 'job_url'")
    print()
    print("📖 See RAG_SETUP_GUIDE.md for detailed instructions")


def create_full_directory_structure(base_dir: pathlib.Path):
    """Create comprehensive directory structure"""
    directories = [
        "career_data",
        "career_data/experience",
        "career_data/skills",
        "career_data/projects",
        "career_data/achievements",
        "code_samples",
        "code_samples/python",
        "code_samples/javascript",
        "code_samples/infrastructure",
        "generated_applications",
        "templates"
    ]

    for dir_path in directories:
        (base_dir / dir_path).mkdir(parents=True, exist_ok=True)


def create_example_personal_info(file_path: pathlib.Path):
    """Create example personal info file"""
    example_data = {
        "name": "Your Full Name",
        "headline": "Your Professional Headline",
        "summary": "Replace this with a comprehensive summary of your professional background, key strengths, and career goals. Be specific about your expertise and achievements.",
        "contact": {
            "email": "your.email@example.com",
            "phone": "+1-234-567-8900",
            "location": "City, State/Country",
            "linkedin": "https://linkedin.com/in/yourprofile",
            "github": "https://github.com/yourusername"
        },
        "specializations": [
            "Your Primary Role",
            "Secondary Expertise"
        ],
        "key_strengths": [
            "Your key strength 1",
            "Your key strength 2"
        ]
    }

    import json
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(example_data, f, indent=2, ensure_ascii=False)


def create_example_files(base_dir: pathlib.Path):
    """Create example career data files"""
    # Example experience file
    exp_file = base_dir / "career_data" / "experience" / "current_role.md"
    exp_content = """# Your Current Role at Company Name
*Start Date - Present*

## Key Responsibilities
- Describe your main responsibilities
- Include specific technologies and tools
- Mention team size and your role

## Achievements
- Quantifiable achievement 1 (with metrics)
- Quantifiable achievement 2 (with metrics)
- Leadership or impact example

## Technologies Used
- Programming languages
- Frameworks and tools
- Cloud platforms
- Databases

## Impact
Describe the business or technical impact of your work.
"""
    exp_file.write_text(exp_content, encoding='utf-8')

    # Example skills file
    skills_file = base_dir / "career_data" / "skills" / "technical_skills.md"
    skills_content = """# Technical Skills

## Programming Languages
- **Python**: Advanced proficiency, 5+ years experience
  - Data science: pandas, numpy, scikit-learn
  - Web development: Django, FastAPI
  - Automation and scripting

## Cloud Platforms
- **AWS**: EC2, S3, Lambda, RDS, CloudFormation
- **GCP**: Compute Engine, BigQuery, Cloud Functions

## Tools & Technologies
- Docker, Kubernetes
- Git, CI/CD pipelines
- SQL and NoSQL databases
"""
    skills_file.write_text(skills_content, encoding='utf-8')

    # Example project file
    project_file = base_dir / "career_data" / "projects" / "key_project.md"
    project_content = """# Major Project Name

## Overview
Brief description of the project and its purpose.

## Technical Architecture
- Frontend: Technologies used
- Backend: Technologies used
- Database: Technologies used
- Infrastructure: Deployment and scaling

## Key Features
- Feature 1 with impact
- Feature 2 with impact
- Feature 3 with impact

## Results & Impact
- Quantifiable business impact
- Technical achievements
- User adoption metrics

## Technologies Demonstrated
- List of technologies and skills shown
"""
    project_file.write_text(project_content, encoding='utf-8')

    # Example code sample
    code_file = base_dir / "code_samples" / "python" / "example_script.py"
    code_content = '''"""
Example Python script demonstrating your skills

This is a sample file to show the structure.
Replace with your actual code samples.
"""

def main():
    """Main function demonstrating your coding style"""
    print("This is an example of your Python code")
    print("Replace this with actual, meaningful code samples")

if __name__ == "__main__":
    main()
'''
    code_file.write_text(code_content, encoding='utf-8')

    # Create personal info file
    create_example_personal_info(base_dir / "personal_info.json")


if __name__ == "__main__":
    main()
