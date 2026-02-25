"""
Verification script for serverless deployment setup.

This script checks:
1. PostgreSQL connectivity
2. Environment variables
3. Required dependencies
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings


def _status(ok: bool) -> str:
    """Return an ASCII-safe status marker."""
    return "[OK]" if ok else "[FAIL]"


async def verify_database() -> bool:
    """Verify PostgreSQL database connectivity."""
    print("\n=== Database Verification ===")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.DATABASE_URL, echo=False)

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

        print(f"{_status(True)} PostgreSQL connection successful!")
        return True

    except Exception as exc:
        print(f"{_status(False)} PostgreSQL connection failed: {exc}")
        print("\nTo fix this:")
        print("1. Ensure PostgreSQL is installed and running")
        print("2. Check your DATABASE_URL in .env file")
        print("3. For local development: docker-compose up -d")
        print("4. For production: Use managed PostgreSQL from Render/Railway/Vercel")
        return False


def verify_environment_variables() -> bool:
    """Verify required environment variables are set."""
    print("\n=== Environment Variables Verification ===")

    required_vars = {
        "DATABASE_URL": settings.DATABASE_URL,
        "SECRET_KEY": settings.SECRET_KEY,
    }
    optional_vars = {
        "YANDEX_API_KEY": settings.YANDEX_API_KEY,
        "YANDEX_FOLDER_ID": settings.YANDEX_FOLDER_ID,
    }

    all_set = True
    for var_name, var_value in required_vars.items():
        if not var_value or var_value in [
            "",
            "your_api_key",
            "your_folder_id",
            "YOUR_SUPER_SECRET_KEY_CHANGE_ME",
        ]:
            print(f"{_status(False)} {var_name}: Not properly configured")
            all_set = False
            continue

        if "KEY" in var_name or "PASSWORD" in var_name:
            masked = var_value[:4] + "..." + var_value[-4:] if len(var_value) > 8 else "***"
            print(f"{_status(True)} {var_name}: {masked}")
        else:
            print(f"{_status(True)} {var_name}: {var_value}")

    for var_name, var_value in optional_vars.items():
        if not var_value or var_value in ["", "your_api_key", "your_folder_id"]:
            print(f"[WARN] {var_name}: Not configured (optional)")
            continue
        masked = var_value[:4] + "..." + var_value[-4:] if len(var_value) > 8 else "***"
        print(f"{_status(True)} {var_name}: {masked}")

    if not all_set:
        print("\nPlease update your .env file with proper values:")
        print("- DATABASE_URL: PostgreSQL connection string")
        print("- SECRET_KEY: A secure random string for JWT tokens")
    else:
        print("\nOptional variables:")
        print("- YANDEX_API_KEY / YANDEX_FOLDER_ID: needed only for Yandex LLM calls")

    return all_set


def verify_dependencies() -> bool:
    """Verify required Python packages are installed."""
    print("\n=== Dependencies Verification ===")

    required_packages = [
        "fastapi",
        "sqlalchemy",
        "asyncpg",
        "langchain",
        "langchain_community",
        "requests",
        "pydantic_settings",
    ]
    optional_packages = [
        "hypothesis",
        "yandex_chain",
        "yandexcloud",
    ]

    all_installed = True

    def _check_module(module_name: str) -> tuple[bool, str]:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return False, "not found"
        try:
            __import__(module_name)
            return True, ""
        except Exception as exc:  # pragma: no cover - defensive diagnostic path
            return False, str(exc)

    for package in required_packages:
        ok, reason = _check_module(package)
        if ok:
            print(f"{_status(True)} {package}: Installed")
        else:
            print(f"{_status(False)} {package}: {reason}")
            all_installed = False

    for package in optional_packages:
        ok, reason = _check_module(package)
        if ok:
            print(f"{_status(True)} {package}: Installed (optional)")
        else:
            print(f"[WARN] {package}: {reason} (optional)")

    if not all_installed:
        print("\nTo install missing dependencies:")
        print("pip install -r requirements.txt")

    return all_installed


async def main() -> int:
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
    print(f"Dependencies: {_status(deps_ok)}")
    print(f"Environment Variables: {_status(env_ok)}")
    print(f"Database Connection: {_status(db_ok)}")

    if deps_ok and env_ok and db_ok:
        print(f"\n{_status(True)} All checks passed! Ready for development.")
        return 0

    print(f"\n{_status(False)} Some checks failed. Please fix the issues above.")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
