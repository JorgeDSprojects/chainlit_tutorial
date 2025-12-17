"""
Migration script to add thread_id column to conversations table.
Run this script once to update the database schema.
"""
import asyncio
import sqlite3
from src.db.database import DATABASE_URL

async def migrate():
    # Extract the database path from the URL
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    print(f"Migrating database: {db_path}")
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if thread_id column already exists
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'thread_id' in columns:
            print("✅ thread_id column already exists. No migration needed.")
        else:
            # Add the thread_id column
            print("Adding thread_id column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN thread_id VARCHAR UNIQUE
            """)
            conn.commit()
            print("✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
