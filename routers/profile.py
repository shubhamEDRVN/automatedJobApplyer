from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime
import json
from database import get_db, generate_id
from schemas.profile import ProfileCreate, Profile, SkillBase, ProjectBase, Skill, Project

router = APIRouter(prefix="/profile", tags=["profile"])

@router.post("", response_model=Profile, status_code=status.HTTP_201_CREATED)
async def create_or_upsert_profile(profile_data: ProfileCreate):
    conn = get_db()
    c = conn.cursor()
    
    # 1. Check if profile exists
    c.execute("SELECT id FROM profiles WHERE email = ?", (profile_data.email,))
    row = c.fetchone()
    
    if row:
        profile_id = row['id']
        c.execute("""UPDATE profiles SET name=?, phone=?, resume_text=?, linkedin_url=?, github_url=?, portfolio_url=? WHERE id=?""",
                  (profile_data.name, profile_data.phone, profile_data.resume_text, 
                   profile_data.linkedin_url, profile_data.github_url, profile_data.portfolio_url, profile_id))
    else:
        profile_id = generate_id()
        c.execute("""INSERT INTO profiles (id, name, email, phone, resume_text, linkedin_url, github_url, portfolio_url, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (profile_id, profile_data.name, profile_data.email, profile_data.phone, 
                   profile_data.resume_text, profile_data.linkedin_url, profile_data.github_url, 
                   profile_data.portfolio_url, datetime.utcnow().isoformat()))
                   
    # 2. Update skills
    if profile_data.skills is not None:
        c.execute("DELETE FROM skills WHERE profile_id=?", (profile_id,))
        for s in profile_data.skills:
            c.execute("INSERT INTO skills (id, profile_id, skill_name, proficiency_level) VALUES (?, ?, ?, ?)",
                      (generate_id(), profile_id, s.skill_name, s.proficiency_level))
                      
    # 3. Update projects
    if profile_data.projects is not None:
        c.execute("DELETE FROM projects WHERE profile_id=?", (profile_id,))
        for p in profile_data.projects:
            c.execute("INSERT INTO projects (id, profile_id, title, description, tech_stack, url) VALUES (?, ?, ?, ?, ?, ?)",
                      (generate_id(), profile_id, p.title, p.description, 
                       json.dumps(p.tech_stack) if p.tech_stack else '[]', p.url))
                       
    # 4. Update preferences
    if profile_data.preferences is not None:
        c.execute("DELETE FROM preferences WHERE profile_id=?", (profile_id,))
        pref = profile_data.preferences
        c.execute("INSERT INTO preferences (id, profile_id, roles_wanted, locations, min_match_score) VALUES (?, ?, ?, ?, ?)",
                  (generate_id(), profile_id, 
                   json.dumps(pref.roles_wanted) if pref.roles_wanted else '[]',
                   json.dumps(pref.locations) if pref.locations else '[]',
                   pref.min_match_score))
                   
    conn.commit()
    conn.close()
    return await get_profile(UUID(profile_id))

@router.get("/{id}", response_model=Profile)
async def get_profile(id: UUID):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM profiles WHERE id=?", (str(id),))
    p_row = c.fetchone()
    
    if not p_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Profile not found")
        
    profile = dict(p_row)
    
    c.execute("SELECT * FROM skills WHERE profile_id=?", (str(id),))
    profile['skills'] = [dict(s) for s in c.fetchall()]
    
    c.execute("SELECT * FROM projects WHERE profile_id=?", (str(id),))
    projects = []
    for pr in c.fetchall():
        pr_dict = dict(pr)
        pr_dict['tech_stack'] = json.loads(pr_dict['tech_stack']) if pr_dict.get('tech_stack') else []
        projects.append(pr_dict)
    profile['projects'] = projects
    
    c.execute("SELECT * FROM preferences WHERE profile_id=?", (str(id),))
    pref_row = c.fetchone()
    if pref_row:
        pref_dict = dict(pref_row)
        pref_dict['roles_wanted'] = json.loads(pref_dict['roles_wanted']) if pref_dict.get('roles_wanted') else []
        pref_dict['locations'] = json.loads(pref_dict['locations']) if pref_dict.get('locations') else []
        profile['preferences'] = pref_dict
    else:
        profile['preferences'] = None
        
    conn.close()
    return profile

@router.put("/{id}/skills", response_model=List[Skill])
async def replace_skills(id: UUID, skills: List[SkillBase]):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM profiles WHERE id=?", (str(id),))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Profile not found")
        
    c.execute("DELETE FROM skills WHERE profile_id=?", (str(id),))
    inserted = []
    if skills:
        for s in skills:
            s_id = generate_id()
            c.execute("INSERT INTO skills (id, profile_id, skill_name, proficiency_level) VALUES (?, ?, ?, ?)",
                      (s_id, str(id), s.skill_name, s.proficiency_level))
            inserted.append({
                "id": s_id, "profile_id": str(id), "skill_name": s.skill_name, "proficiency_level": s.proficiency_level
            })
            
    conn.commit()
    conn.close()
    return inserted

@router.put("/{id}/projects", response_model=List[Project])
async def replace_projects(id: UUID, projects: List[ProjectBase]):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM profiles WHERE id=?", (str(id),))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Profile not found")
        
    c.execute("DELETE FROM projects WHERE profile_id=?", (str(id),))
    inserted = []
    if projects:
        for p in projects:
            p_id = generate_id()
            c.execute("INSERT INTO projects (id, profile_id, title, description, tech_stack, url) VALUES (?, ?, ?, ?, ?, ?)",
                      (p_id, str(id), p.title, p.description, json.dumps(p.tech_stack) if p.tech_stack else '[]', p.url))
            inserted.append({
                "id": p_id, "profile_id": str(id), "title": p.title, "description": p.description, 
                "tech_stack": p.tech_stack, "url": p.url
            })
            
    conn.commit()
    conn.close()
    return inserted
