from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class SkillBase(BaseModel):
    skill_name: str
    proficiency_level: Optional[str] = None

class Skill(SkillBase):
    id: UUID
    profile_id: UUID

class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    tech_stack: Optional[List[str]] = []
    url: Optional[str] = None

class Project(ProjectBase):
    id: UUID
    profile_id: UUID

class PreferenceBase(BaseModel):
    roles_wanted: Optional[List[str]] = []
    locations: Optional[List[str]] = []
    min_match_score: Optional[int] = 0

class Preference(PreferenceBase):
    id: UUID
    profile_id: UUID

class ProfileBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    resume_text: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

class ProfileCreate(ProfileBase):
    skills: Optional[List[SkillBase]] = []
    projects: Optional[List[ProjectBase]] = []
    preferences: Optional[PreferenceBase] = None

class Profile(ProfileBase):
    id: UUID
    created_at: datetime
    skills: List[Skill] = []
    projects: List[Project] = []
    preferences: Optional[Preference] = None
