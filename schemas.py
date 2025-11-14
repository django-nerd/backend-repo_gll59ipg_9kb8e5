"""
Database Schemas for AI Portfolio Builder

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name by convention.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    name: str
    email: EmailStr
    username: str = Field(..., description="Unique handle for public portfolio URL")
    avatar_url: Optional[str] = None
    headline: Optional[str] = None
    social: Dict[str, Optional[str]] = Field(
        default_factory=lambda: {"github": None, "linkedin": None, "website": None}
    )


class PortfolioSection(BaseModel):
    key: str  # summary, skills, projects, experience, education, achievements, contact
    title: str
    content: Any  # string or structured list


class Portfolio(BaseModel):
    owner_email: EmailStr
    username: str = Field(..., description="Public slug e.g., yoursite.com/username")
    name: str
    theme: str = Field("modern", description="minimal|modern|creative|dark")
    dark_mode: bool = False
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    sections: List[PortfolioSection] = []
    assets: Dict[str, Any] = Field(default_factory=dict)  # images, logos, etc.


class AIGenerateInput(BaseModel):
    name: str
    skills: List[str] = []
    education: List[str] = []
    projects: List[str] = []
    experience: List[str] = []
    achievements: List[str] = []
    contact_email: Optional[EmailStr] = None
    tone: str = Field("professional", description="tone for AI suggestions")


class AIGenerateResult(BaseModel):
    summary: str
    skills: List[str]
    projects: List[Dict[str, Any]]
    experience: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    achievements: List[str]
    contact: Dict[str, Any]
    suggestions: List[str]
