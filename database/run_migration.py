#!/usr/bin/env python3
"""
Kör conversation memory migrations i Supabase
"""
import os
import sys
from pathlib import Path
from supabase import create_client

# Lägg till parent directory i path för att kunna importera
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Ladda miljövariabler
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def run_migration():
    """Kör SQL migration för conversation memory"""

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL eller SUPABASE_KEY saknas i .envy")
        return False

    # Läs SQL-filen
    sql_file = Path(__file__).parent / "conversation_schema.sql"

    if not sql_file.exists():
        print(f"❌ Kunde inte hitta {sql_file}")
        return False

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Supabase Python-klienten kan inte köra raw SQL direkt
    # Användaren måste köra detta i Supabase Dashboard istället
    print("\n" + "="*60)
    print("SUPABASE MIGRATION - conversation_memory")
    print("="*60)
    print("\n⚠️  Supabase Python-klienten stödjer inte raw SQL execution.")
    print("\n📋 Kopiera SQL-koden nedan och kör den i Supabase Dashboard:")
    print("   👉 https://supabase.com/dashboard/project/[ditt-projekt]/sql\n")
    print("-"*60)
    print(sql_content)
    print("-"*60)
    print("\n✅ När du kört SQL:en är minnesystemet redo att använda!\n")

    return True

if __name__ == "__main__":
    run_migration()
