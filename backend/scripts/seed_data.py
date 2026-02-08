"""Seed default projects and settings into DynamoDB."""
import sys
import os
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load env if .env exists
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

from app.db import put_item, get_item
from app.config import DEFAULT_SETTINGS

DEFAULT_PROJECTS = [
    {
        "area": "teaching", "name": "BADM 358",
        "description": "Big Data Platforms",
        "match_keywords": ["358", "big data", "infrastructure"],
    },
    {
        "area": "teaching", "name": "BADM 558",
        "description": "Business Data Mining",
        "match_keywords": ["558", "data mining", "mining", "classification"],
    },
    {
        "area": "teaching", "name": "BADM 550",
        "description": "Business Practicum",
        "match_keywords": ["550", "practicum"],
    },
    {
        "area": "teaching", "name": "BADM 576",
        "description": "Data Science & Analytics",
        "match_keywords": ["576", "data science", "analytics"],
    },
    {
        "area": "research", "name": "AI Transparency",
        "description": "Reasoning visibility studies",
        "match_keywords": ["transparency", "reasoning visibility", "AI study", "prolific"],
    },
    {
        "area": "research", "name": "Signaling Theory",
        "description": "Post-rejection withdrawal",
        "match_keywords": ["signaling", "rejection", "withdrawal"],
    },
    {
        "area": "research", "name": "Healthcare Platform",
        "description": "Price transparency",
        "match_keywords": ["healthcare", "price transparency", "hospital"],
    },
    {
        "area": "personal", "name": "Family",
        "description": "Household & kids",
        "match_keywords": ["daughter", "kids", "wife", "family", "school play", "household"],
    },
    {
        "area": "personal", "name": "Finances",
        "description": "Budget, taxes, insurance",
        "match_keywords": ["taxes", "tax", "W2", "1099", "accountant", "budget", "insurance"],
    },
    {
        "area": "personal", "name": "Health",
        "description": "Doctors, wellness",
        "match_keywords": ["dentist", "doctor", "appointment", "physical", "wellness",
                           "exercise", "gym", "food", "protein", "sleep"],
    },
    {
        "area": "admin", "name": "Department",
        "description": "Gies admin tasks",
        "match_keywords": ["dean", "committee", "department", "gies", "faculty"],
    },
]


def seed():
    now = datetime.utcnow().isoformat()

    # Check if already seeded
    existing = get_item("SETTINGS", "USER")
    if existing:
        print("Data already seeded (settings exist). Skipping.")
        return

    # Seed projects
    print("Seeding projects...")
    for proj in DEFAULT_PROJECTS:
        pid = str(uuid.uuid4())
        item = {
            "pk": "PROJECT",
            "sk": pid,
            "id": pid,
            **proj,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }
        put_item(item)
        print(f"  Created: {proj['name']} ({pid[:8]}...)")

    # Seed settings
    print("Seeding settings...")
    settings_item = {
        "pk": "SETTINGS",
        "sk": "USER",
        **DEFAULT_SETTINGS,
        "created_at": now,
        "updated_at": now,
    }
    put_item(settings_item)
    print("  Settings created.")

    print("\nSeed complete!")


if __name__ == "__main__":
    seed()
