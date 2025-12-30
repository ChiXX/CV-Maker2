"""RAG (Retrieval-Augmented Generation) system for personal career data"""

import asyncio
import json
import pathlib
from typing import Dict, Any, List, Optional

try:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
except ImportError:
    Chroma = None
    OpenAIEmbeddings = None
    RecursiveCharacterTextSplitter = None
    Document = None

from typing import Dict, Any
from rich.console import Console


class RAGSystem:
    """Manages personal career data for CV customization"""

    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.console = Console()

        # Check if langchain is available
        if not all([Chroma, OpenAIEmbeddings, RecursiveCharacterTextSplitter, Document]):
            self.console.print("[yellow]⚠️  LangChain dependencies not found. RAG features will be limited.[/yellow]")
            self.vectorstore = None
        else:
            self.vectorstore = None
            self.embeddings = OpenAIEmbeddings(model=config["embedding_model"])
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=config["chunk_size"],
                chunk_overlap=config["chunk_overlap"],
            )

    async def initialize_database(self) -> None:
        """Initialize and populate the RAG database"""
        if not self.vectorstore:
            self._initialize_vectorstore()

        # Load and process personal data
        documents = []

        # Load personal info file
        if self.config["personal_info_file"] and self.config["personal_info_file"].exists():
            docs = self._load_personal_info_file()
            documents.extend(docs)

        # Load career data directory
        if self.config["career_data_dir"] and self.config["career_data_dir"].exists():
            docs = self._load_career_data_directory()
            documents.extend(docs)

        # Load code samples directory
        if self.config["code_samples_dir"] and self.config["code_samples_dir"].exists():
            docs = self._load_code_samples_directory()
            documents.extend(docs)

        # Add documents to vector store
        if documents:
            if self.verbose:
                self.console.print(f"[dim]Adding {len(documents)} documents to vector store...[/dim]")

            self.vectorstore.add_documents(documents)

            if self.verbose:
                self.console.print("[dim]Vector store updated successfully[/dim]")

    async def get_relevant_context(self, job_info: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant context for CV customization based on job requirements"""
        if not self.vectorstore:
            return self._get_fallback_context()

        # Create search query from job info
        query = self._create_search_query(job_info)

        if self.verbose:
            self.console.print(f"[dim]Searching for relevant experience: {query}[/dim]")

        try:
            # Search for relevant documents
            docs = self.vectorstore.similarity_search(query, k=5)

            # Organize results by category
            context = {
                'personal_info': [],
                'experience': [],
                'skills': [],
                'projects': [],
                'education': [],
                'code_samples': [],
            }

            for doc in docs:
                category = doc.metadata.get('category', 'general')
                if category in context:
                    context[category].append({
                        'content': doc.page_content,
                        'metadata': doc.metadata,
                        'score': getattr(doc, 'score', None)
                    })

            return context

        except Exception as e:
            if self.verbose:
                self.console.print(f"[dim]Vector search failed: {str(e)}, using fallback[/dim]")
            return self._get_fallback_context()

    def _initialize_vectorstore(self) -> None:
        """Initialize the vector store"""
        if not Chroma:
            return

        # Create vector store directory if it doesn't exist
        self.config["vector_store_path"].mkdir(parents=True, exist_ok=True)

        # Initialize Chroma vector store
        self.vectorstore = Chroma(
            persist_directory=str(self.config["vector_store_path"]),
            embedding_function=self.embeddings,
        )

    def _load_personal_info_file(self) -> List[Document]:
        """Load personal information from file"""
        documents = []

        try:
            with open(self.config["personal_info_file"], 'r', encoding='utf-8') as f:
                if self.config["personal_info_file"].suffix.lower() in ['.json']:
                    data = json.load(f)
                    content = json.dumps(data, indent=2)
                else:
                    content = f.read()

            doc = Document(
                page_content=content,
                metadata={
                    'source': str(self.config["personal_info_file"]),
                    'category': 'personal_info',
                    'type': 'personal_data'
                }
            )
            documents.append(doc)

        except Exception as e:
            self.console.print(f"[red]Error loading personal info file: {str(e)}[/red]")

        return documents

    def _load_career_data_directory(self) -> List[Document]:
        """Load career data from directory"""
        documents = []

        if not self.config["career_data_dir"].exists():
            return documents

        for file_path in self.config["career_data_dir"].rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in ['.txt', '.md', '.json', '.yaml', '.yml']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        if file_path.suffix.lower() in ['.json']:
                            data = json.load(f)
                            content = json.dumps(data, indent=2)
                        else:
                            content = f.read()

                    # Determine category based on filename/content
                    category = self._determine_career_category(file_path, content)

                    doc = Document(
                        page_content=content,
                        metadata={
                            'source': str(file_path),
                            'category': category,
                            'filename': file_path.name,
                            'type': 'career_data'
                        }
                    )
                    documents.append(doc)

                except Exception as e:
                    self.console.print(f"[red]Error loading {file_path}: {str(e)}[/red]")

        return documents

    def _load_code_samples_directory(self) -> List[Document]:
        """Load code samples from directory"""
        documents = []

        if not self.config["code_samples_dir"].exists():
            return documents

        for file_path in self.config["code_samples_dir"].rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Add file extension info for better context
                    doc = Document(
                        page_content=content,
                        metadata={
                            'source': str(file_path),
                            'category': 'code_samples',
                            'filename': file_path.name,
                            'language': file_path.suffix[1:],  # Remove the dot
                            'type': 'code'
                        }
                    )
                    documents.append(doc)

                except Exception as e:
                    self.console.print(f"[red]Error loading code sample {file_path}: {str(e)}[/red]")

        return documents

    def _determine_career_category(self, file_path: pathlib.Path, content: str) -> str:
        """Determine the category of career data based on filename and content"""
        filename = file_path.name.lower()
        content_lower = content.lower()

        if any(word in filename for word in ['experience', 'work', 'job']):
            return 'experience'
        elif any(word in filename for word in ['skill', 'tech']):
            return 'skills'
        elif any(word in filename for word in ['project', 'portfolio']):
            return 'projects'
        elif any(word in filename for word in ['education', 'degree', 'university']):
            return 'education'
        elif 'experience' in content_lower and 'work' in content_lower:
            return 'experience'
        elif 'skill' in content_lower or 'technology' in content_lower:
            return 'skills'
        elif 'project' in content_lower:
            return 'projects'
        else:
            return 'general'

    def _create_search_query(self, job_info: Dict[str, Any]) -> str:
        """Create a search query from job information"""
        title = job_info.get('title', '')
        company = job_info.get('company', '')
        description = job_info.get('description', '')

        # Extract key skills and technologies from job description
        skills_keywords = self._extract_keywords(description)

        # Build query
        query_parts = []

        if title:
            query_parts.append(f"job title: {title}")

        if company:
            query_parts.append(f"company: {company}")

        if skills_keywords:
            query_parts.append(f"skills: {' '.join(skills_keywords[:5])}")  # Limit to top 5

        if description:
            # Take first 200 characters of description
            desc_preview = description[:200]
            query_parts.append(f"description: {desc_preview}")

        return " ".join(query_parts)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract potential skill keywords from text"""
        # Common tech skills and keywords
        common_skills = [
            'python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'typescript',
            'react', 'angular', 'vue', 'node', 'django', 'flask', 'spring', 'dotnet',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'sql', 'nosql', 'mongodb',
            'machine learning', 'ai', 'data science', 'tensorflow', 'pytorch',
            'agile', 'scrum', 'devops', 'ci/cd', 'git', 'linux', 'cloud'
        ]

        found_skills = []
        text_lower = text.lower()

        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill)

        return found_skills

    def _get_fallback_context(self) -> Dict[str, Any]:
        """Return fallback context when RAG is not available"""
        # Try to load any available user personal_info.json files as a degraded fallback
        context = {
            'personal_info': [],
            'experience': [],
            'skills': [],
            'projects': [],
            'education': [],
            'code_samples': [],
            'fallback': True,
            'message': 'RAG system not available, using available personal_info files as fallback'
        }

        try:
            users_dir = pathlib.Path('./users')
            if users_dir.exists() and users_dir.is_dir():
                for user_dir in users_dir.iterdir():
                    pinfo = user_dir / 'personal_info.json'
                    if pinfo.exists():
                        try:
                            with open(pinfo, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            # Add a simple personal info record
                            context['personal_info'].append({
                                'source': str(pinfo),
                                'content': data
                            })

                            # Extract skills, experiences, projects, education if present
                            if isinstance(data.get('skills'), list):
                                for s in data.get('skills'):
                                    context['skills'].append({'name': s, 'source': str(pinfo)})

                            if isinstance(data.get('experiences'), list):
                                for exp in data.get('experiences'):
                                    # Normalize experience content to string for downstream consumers
                                    content_str = json.dumps(exp, ensure_ascii=False) if isinstance(exp, (dict, list)) else str(exp)
                                    context['experience'].append({'content': content_str, 'source': str(pinfo)})

                            if isinstance(data.get('projects'), list):
                                for proj in data.get('projects'):
                                    content_str = json.dumps(proj, ensure_ascii=False) if isinstance(proj, (dict, list)) else str(proj)
                                    context['projects'].append({'content': content_str, 'source': str(pinfo)})

                            if isinstance(data.get('education'), list):
                                for edu in data.get('education'):
                                    content_str = json.dumps(edu, ensure_ascii=False) if isinstance(edu, (dict, list)) else str(edu)
                                    context['education'].append({'content': content_str, 'source': str(pinfo)})

                        except Exception as e:
                            if self.verbose:
                                self.console.print(f"[yellow]Warning: failed to read {pinfo}: {e}[/yellow]")
        except Exception:
            # If anything goes wrong, fall back to empty context
            pass

        return context
