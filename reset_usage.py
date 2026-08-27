import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def reset_usage():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.lumiere_gallery
    
    # Find admin user
    admin = await db.users.find_one({"email": "admin@lumiere.studio"})
    if admin:
        print(f"Admin user found: {admin['email']}")
        print(f"Current usage: {admin.get('usage', {})}")
        
        # Reset usage counters
        result = await db.users.update_one(
            {"email": "admin@lumiere.studio"},
            {"$set": {"usage": {"galleries_created": 0, "gdrive_created": 0, "clients_created": 0}}}
        )
        print(f"Updated {result.modified_count} document(s)")
        
        # Verify
        admin = await db.users.find_one({"email": "admin@lumiere.studio"})
        print(f"New usage: {admin.get('usage', {})}")
    else:
        print("Admin user not found")
    
    client.close()

asyncio.run(reset_usage())
