"""Configuration management for CV Agent"""

import os
import pathlib
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field


class RAGConfig(BaseModel):
    """Configuration for the RAG database"""
    vector_store_path: pathlib.Path = Field(default=pathlib.Path("./rag_store"))
    embedding_model: str = Field(default="text-embedding-3-small")
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    personal_info_file: Optional[pathlib.Path] = Field(default=None)
    career_data_dir: Optional[pathlib.Path] = Field(default=None)
    code_samples_dir: Optional[pathlib.Path] = Field(default=None)

    def get_user_paths(self, user_name: str) -> Dict[str, pathlib.Path]:
        """Get user-specific paths for RAG data"""
        user_dir = pathlib.Path(f"./users/{user_name}")
        return {
            "user_dir": user_dir,
            "vector_store": user_dir / "rag_store",
            "personal_info": user_dir / "personal_info.json",
            "career_data": user_dir / "career_data",
            "code_samples": user_dir / "code_samples",
            "cv_template": user_dir / "cv_template.yaml",
            "config_file": user_dir / "config.yaml"
        }


class LLMConfig(BaseModel):
    """Configuration for LLM settings"""
    provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openrouter"))
    model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4000")))
    api_key_env_var: str = Field(default="OPENROUTER_API_KEY")
    base_url: Optional[str] = Field(default="https://openrouter.ai/api/v1")

    @classmethod
    def get_development_config(cls) -> "LLMConfig":
        """Get LLM config optimized for development (fast, cheap)"""
        return cls(
            provider="openrouter",
            model=os.getenv("LLM_MODEL_DEV", "meta-llama/llama-3.2-3b-instruct"),
            temperature=0.1,
            max_tokens=2000,  # Lower for faster responses
            api_key_env_var="OPENROUTER_API_KEY"
        )

    @classmethod
    def get_production_config(cls) -> "LLMConfig":
        """Get LLM config optimized for production (high quality)"""
        return cls(
            provider="openrouter",
            model=os.getenv("LLM_MODEL_PROD", "anthropic/claude-3.5-sonnet"),
            temperature=0.1,
            max_tokens=4000,
            api_key_env_var="OPENROUTER_API_KEY"
        )


class TranslationConfig(BaseModel):
    """Configuration for translation services"""
    provider: str = Field(default="google")  # google, azure, openai
    api_key_env_var: str = Field(default="GOOGLE_TRANSLATE_API_KEY")


class CVConfig(BaseModel):
    """Configuration for CV generation"""
    template_dir: pathlib.Path = Field(default=pathlib.Path("./cv_templates"))
    base_cv_file: pathlib.Path = Field(default=pathlib.Path("./base_cv.yaml"))
    theme: str = Field(default="classic")


class CVCLConfig(BaseModel):
    """Global configuration for CV and Cover Letter templates"""
    cv: CVConfig = Field(default_factory=CVConfig)
    cover_letter_template: pathlib.Path = Field(default=pathlib.Path("./cv_templates/cover_letter_template.md"))
    output_dir: pathlib.Path = Field(default=pathlib.Path("./generated_applications"))

    @classmethod
    def load(cls, config_file: pathlib.Path = pathlib.Path("./cv_config.yaml")) -> "CVCLConfig":
        """Load CV/CL configuration from YAML file"""
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                return cls(**data)
            except Exception as e:
                print(f"Warning: Could not load CV config {config_file}: {str(e)}")
                return cls()
        else:
            # Return default configuration
            return cls()


class Config(BaseModel):
    """Main configuration class for user-specific settings"""
    user_name: str = Field(default="default_user")
    rag: RAGConfig = Field(default_factory=RAGConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)

    @classmethod
    def load(cls, config_file: Optional[pathlib.Path] = None) -> "Config":
        """Load configuration from YAML file"""
        if config_file is None:
            # Try to find default config files
            default_paths = [
                pathlib.Path("./cv-agent-config.yaml"),
                pathlib.Path("./cv-agent-config.yml"),
                pathlib.Path("~/.cv-agent-config.yaml").expanduser(),
            ]
            for path in default_paths:
                if path.exists():
                    config_file = path
                    break

        if config_file and config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return cls(**data)
        else:
            # Return default configuration
            return cls()

    def save(self, config_file: pathlib.Path) -> None:
        """Save configuration to YAML file"""
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
