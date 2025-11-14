import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from database import db, create_document, get_documents
from schemas import User, Portfolio, PortfolioSection, AIGenerateInput, AIGenerateResult
import requests

app = FastAPI(title="AI Portfolio Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "AI Portfolio Builder Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            response["connection_status"] = "Connected"
            collections = db.list_collection_names()
            response["collections"] = collections[:10]
            response["database"] = "✅ Connected & Working"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ---- AI Utilities ----

class AISuggestRequest(BaseModel):
    text: str
    tone: str = "professional"


AI_PROVIDER_URL = os.getenv("AI_API_URL")
AI_API_KEY = os.getenv("AI_API_KEY")


def call_llm(prompt: str) -> str:
    """Call external LLM provider if configured; otherwise return a heuristic draft."""
    if AI_PROVIDER_URL and AI_API_KEY:
        try:
            resp = requests.post(
                AI_PROVIDER_URL,
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"prompt": prompt, "max_tokens": 600}
            )
            if resp.ok:
                data = resp.json()
                # Expect {"text": "..."} or OpenAI-like choices
                if isinstance(data, dict) and data.get("text"):
                    return data["text"]
                if data.get("choices"):
                    return data["choices"][0]["text"]
            return f"Draft (AI service unavailable): {prompt[:280]}..."
        except Exception:
            return f"Draft (AI error): {prompt[:280]}..."
    # Fallback locally crafted summary
    return (
        "Professional, impact-driven candidate. Blends technical depth with clear communication, "
        "drives outcomes through projects, internships, and community work. Values clarity, "
        "collaboration, and continuous learning."
    )


# ---- API: AI generation endpoints ----

@app.post("/api/generate", response_model=AIGenerateResult)
def generate_portfolio(data: AIGenerateInput):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    # Compose prompts
    skills_str = ", ".join(data.skills) or "(skills not provided)"
    projects_bullets = "\n".join(f"- {p}" for p in data.projects)
    exp_bullets = "\n".join(f"- {e}" for e in data.experience)
    edu_bullets = "\n".join(f"- {e}" for e in data.education)

    summary_prompt = (
        f"Write a {data.tone} 3-4 sentence professional summary for {name}. "
        f"Highlight strengths from skills: {skills_str}. Audience: recruiters and hiring managers."
    )
    summary = call_llm(summary_prompt)

    suggestions_prompt = (
        "Given the user's inputs (skills, projects, experience, education), suggest 5 concise improvements "
        "that strengthen clarity, impact, and ATS readiness. Use imperative tone."
    )
    suggestions_text = call_llm(suggestions_prompt)
    suggestions = [s.strip("- • ") for s in suggestions_text.split("\n") if s.strip()][:5]

    # Structure sections
    projects_struct = [
        {"title": p.split(" - ")[0], "description": p, "impact": ""} for p in data.projects
    ]
    experience_struct = [
        {"role": e.split(" at ")[0], "details": e, "achievements": []} for e in data.experience
    ]
    education_struct = [
        {"program": e, "institution": "", "year": ""} for e in data.education
    ]

    result = AIGenerateResult(
        summary=summary,
        skills=data.skills or [],
        projects=projects_struct,
        experience=experience_struct,
        education=education_struct,
        achievements=data.achievements or [],
        contact={"email": data.contact_email or "", "name": name},
        suggestions=suggestions,
    )
    return result


@app.post("/api/suggest")
def ai_suggest(payload: AISuggestRequest):
    prompt = (
        f"Improve the following text for {payload.tone} tone. Keep it concise, clear, and action-oriented.\n\n"
        f"Text: {payload.text}"
    )
    improved = call_llm(prompt)
    return {"improved": improved}


# ---- API: Portfolio persistence ----

class SavePortfolioRequest(BaseModel):
    owner_email: EmailStr
    username: str
    name: str
    theme: str
    dark_mode: bool = False
    sections: List[PortfolioSection]
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    assets: Dict[str, Any] = {}


@app.post("/api/portfolio/save")
def save_portfolio(payload: SavePortfolioRequest):
    # Ensure username uniqueness
    exists = get_documents("portfolio", {"username": payload.username})
    if exists:
        # Upsert-like behavior: replace latest
        try:
            from bson import ObjectId
            # delete existing then insert new for simplicity
            db.portfolio.delete_many({"username": payload.username})
        except Exception:
            pass
    pid = create_document("portfolio", payload.model_dump())
    return {"id": pid, "username": payload.username}


@app.get("/api/portfolio/{username}")
def get_portfolio(username: str):
    docs = get_documents("portfolio", {"username": username})
    if not docs:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    doc = docs[-1]
    doc["_id"] = str(doc.get("_id"))
    return doc


# ---- API: File upload stubs ----

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # In this environment we store to DB as metadata only; in production use S3 or similar
    content = await file.read()
    meta = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
    }
    fid = create_document("uploads", meta)
    return {"file_id": fid, "meta": meta}


# ---- Public hosting route (server-side render JSON → consumed by frontend router) ----

@app.get("/u/{username}")
def public_portfolio(username: str):
    # Same as get_portfolio but optimized for public
    return get_portfolio(username)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
