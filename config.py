"""Simplified configuration management for CV Agent"""

import os
import pathlib
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field


def get_llm_config() -> Dict[str, Any]:
    """Get hardcoded LLM configuration optimized for CV generation"""
    return {
        "provider": "openrouter",
        "model": "deepseek/deepseek-v3.2",
        "temperature": 0.1,
        "max_tokens": 4000,
        "api_key_env_var": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1"
    }


def get_user_paths(user_name: str) -> Dict[str, pathlib.Path]:
    """Get user-specific paths for a given user"""
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


def get_rag_config(user_name: str) -> Dict[str, Any]:
    """Get hardcoded RAG configuration optimized for CV generation"""
    user_paths = get_user_paths(user_name)
    return {
        "vector_store_path": user_paths["vector_store"],
        "embedding_model": "text-embedding-3-small",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "personal_info_file": user_paths["personal_info"],
        "career_data_dir": user_paths["career_data"],
        "code_samples_dir": user_paths["code_samples"]
    }


# Utility functions for personal info (only used in setup commands)
def load_user_personal_info(user_name: str) -> Dict[str, Any]:
    """Load user's personal information from file"""
    user_paths = get_user_paths(user_name)
    personal_info_file = user_paths["personal_info"]
    if personal_info_file.exists():
        try:
            with open(personal_info_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load personal info {personal_info_file}: {str(e)}")
            return {}
    return {}





class Config:
    """Simplified config class - just user name and global settings"""
    def __init__(self, user_name: str):
        self.user_name = user_name
        self.llm = get_llm_config()
        self.rag = get_rag_config(user_name)

    @property
    def user_paths(self) -> Dict[str, pathlib.Path]:
        """Get user-specific paths"""
        return get_user_paths(self.user_name)

    def get_user_paths(self, user_name: str) -> Dict[str, pathlib.Path]:
        """Get user-specific paths (for backward compatibility)"""
        return get_user_paths(user_name)


CV_TEMPLATE_DIR = pathlib.Path("./templates")
CV_TEMPLATE = CV_TEMPLATE_DIR / "cv.yaml"
COVER_LETTER_TEMPLATE = CV_TEMPLATE_DIR / "cl.yaml"
OUTPUT_DIR = pathlib.Path("./generated_applications")


class CVCLConfig:
    """Simple config class that provides hardcoded template paths"""

    def __init__(self):
        # Create a simple object with the same interface as before
        self.cv = type('CVConfig', (), {
            'template_dir': CV_TEMPLATE_DIR,
            'base_cv_file': CV_TEMPLATE,
            'theme': 'classic'
        })()
        self.cover_letter_template = COVER_LETTER_TEMPLATE
        self.output_dir = OUTPUT_DIR
