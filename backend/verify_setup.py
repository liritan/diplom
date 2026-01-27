"""
Verification script for serverless deployment setup.

This script checks:
1. PostgreSQL connectivity
2. Environment variables
3. Required dependencies
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings


async def verify_database():
    """Verify PostgreSQL database connectivity."""
    print("\n=== Database Verification ===")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            await result.fetchone()
            
        print("✓ PostgreSQL connection successful!")
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {str(e)}")
        print("\nTo fix this:")
        print("1. Ensure PostgreSQL is installed and running")
        print("2. Check your DATABASE_URL in .env file")
        print("3. For local development: docker-compose up -d")
        print("4. For production: Use managed PostgreSQL from Render/Railway/Vercel")
        return False


def verify_environment_variables():
    """Verify required environment variables are set."""
    print("\n=== Environment Variables Verification ===")
    
    required_vars = {
        "DATABASE_URL": settings.DATABASE_URL,
        "YANDEX_API_KEY": settings.YANDEX_API_KEY,
        "YANDEX_FOLDER_ID": settings.YANDEX_FOLDER_ID,
        "SECRET_KEY": settings.SECRET_KEY,
    }
    
    all_set = True
    for var_name, var_value in required_vars.items():
        if not var_value or var_value in ["", "your_api_key", "your_folder_id", "YOUR_SUPER_SECRET_KEY_CHANGE_ME"]:
            print(f"✗ {var_name}: Not properly configured")
            all_set = False
        else:
            # Mask sensitive values
            if "KEY" in var_name or "PASSWORD" in var_name:
                masked = var_value[:4] + "..." + var_value[-4:] if len(var_value) > 8 else "***"
                print(f"✓ {var_name}: {masked}")
            else:
                print(f"✓ {var_name}: {var_value}")
    
    if not all_set:
        print("\nPlease update your .env file with proper values:")
        print("- DATABASE_URL: PostgreSQL connection string")
        print("- YANDEX_API_KEY: Your Yandex Cloud API key")
        print("- YANDEX_FOLDER_ID: Your Yandex Cloud folder ID")
        print("- SECRET_KEY: A secure random string for JWT tokens")
    
    return all_set


def verify_dependencies():
    """Verify required Python packages are installed."""
    print("\n=== Dependencies Verification ===")
    
    required_packages = [
        "fastapi",
        "sqlalchemy",
        "asyncpg",
        "hypothesis",
        "langchain",
        "yandex_chain",
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}: Installed")
        except ImportError:
            print(f"✗ {package}: Not installed")
            all_installed = False
    
    if not all_installed:
        print("\nTo install missing dependencies:")
        print("pip install -r requirements.txt")
    
    return all_installed


async def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Serverless Deployment Setup Verification")
    print("=" * 60)
    
    deps_ok = verify_dependencies()
    env_ok = verify_environment_variables()
    db_ok = await verify_database()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Dependencies: {'✓ OK' if deps_ok else '✗ Issues found'}")
    print(f"Environment Variables: {'✓ OK' if env_ok else '✗ Issues found'}")
    print(f"Database Connection: {'✓ OK' if db_ok else '✗ Issues found'}")
    
    if deps_ok and env_ok and db_ok:
        print("\n✓ All checks passed! Ready for development.")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
