"""Update profile preferences to focus on internships and fresher roles."""
import sqlite3
import json

conn = sqlite3.connect("internships.db")
c = conn.cursor()

PROFILE_ID = "shubham_mehta_01"

# Update resume text to emphasize fresher/intern status
resume_update = """3rd year B.Tech Computer Science student at Medicaps University, Indore (graduating 2027). Full Stack Developer with strong project portfolio including SevaAI (MERN + Gemini API + LangChain), Uber Clone (React + Node + Socket.IO), Profit Paybook Pro (freelance SaaS for US client). Tech skills: Java, Python, JavaScript, React.js, Node.js, Express.js, Spring Boot, MongoDB, MySQL, AWS, Docker, Git. Seeking INTERNSHIP opportunities in software development, web development, or backend engineering. Available for immediate joining. Open to remote and in-office internships."""

c.execute("UPDATE profiles SET resume_text=? WHERE id=?", (resume_update, PROFILE_ID))

# Update preferred roles to internship-focused keywords
roles = [
    "Software Development Intern",
    "Web Development Intern", 
    "Full Stack Developer Intern",
    "Backend Developer Intern",
    "Python Developer Intern",
    "MERN Stack Intern",
    "SDE Intern",
    "Java Developer Intern",
    "Software Engineer Intern"
]

locations = ["Remote", "Indore", "Bangalore", "Mumbai", "Delhi", "Pune", "Hyderabad", "Work From Home"]

c.execute("UPDATE preferences SET roles_wanted=?, locations=?, min_match_score=? WHERE profile_id=?",
          (json.dumps(roles), json.dumps(locations), 50, PROFILE_ID))

conn.commit()

# Verify
c.execute("SELECT roles_wanted, min_match_score FROM preferences WHERE profile_id=?", (PROFILE_ID,))
row = c.fetchone()
print(f"Roles: {row[0]}")
print(f"Min score: {row[1]}")

# Reset jobs and cover letters for fresh scoring with new prompts
c.execute("UPDATE jobs SET status='new', applied_at=NULL, apply_method=NULL, apply_status=NULL")
c.execute("DELETE FROM cover_letters")
conn.commit()
c.execute("SELECT COUNT(*) FROM jobs WHERE status='new'")
print(f"Reset {c.fetchone()[0]} jobs for re-scoring")

conn.close()
print("Done! Preferences updated for internship-focused search.")
