"""CLI commands for API Gateway management."""

import asyncio
import sys

from app.auth import generate_api_key
from app.database import get_db_context
from app.models import APIKey


async def create_api_key_command(name: str, scopes: list[str] = None) -> None:
    """Create a new API key."""
    if scopes is None:
        scopes = ["read", "write", "admin"]

    full_key, key_prefix, key_hash = generate_api_key()

    async with get_db_context() as db:
        new_key = APIKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes,
            rate_limit=1000,
        )

        db.add(new_key)
        await db.commit()
        await db.refresh(new_key)

        print(f"\n✅ API Key created successfully!")
        print(f"   Name: {new_key.name}")
        print(f"   ID: {new_key.id}")
        print(f"   Scopes: {', '.join(new_key.scopes)}")
        print(f"\n🔑 API Key (save this, it won't be shown again):")
        print(f"   {full_key}\n")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command> [args]")
        print("\nCommands:")
        print("  create-api-key --name <name>  Create a new API key")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create-api-key":
        name = None
        for i, arg in enumerate(sys.argv):
            if arg == "--name" and i + 1 < len(sys.argv):
                name = sys.argv[i + 1]
                break

        if not name:
            print("Error: --name argument required")
            sys.exit(1)

        asyncio.run(create_api_key_command(name))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
