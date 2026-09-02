"""One-shot DB bootstrap for AskBase.

Called by start.bat. Safe to run repeatedly:
  - creates missing tables (SQLAlchemy create_all, idempotent)
  - ensures the admin account exists and its password matches settings

Exit codes:
  0 = OK
  1 = failed (start.bat will abort)
"""

import asyncio
import os
import sys

# Make "app" importable no matter where the script is launched from.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Keep console output ASCII-only: start.bat runs under a GBK code page on
# Chinese Windows and non-ASCII prints turn into mojibake / UnicodeEncodeError.


async def main() -> int:
    from app.database import async_session_factory, engine, init_db
    from app.services.auth_service import seed_admin

    # config sets SQL echo on, which floods the bootstrap console
    engine.echo = False

    print("[init] creating tables if missing ...")
    await init_db()
    print("[init] tables ready")

    print("[init] seeding admin account ...")
    async with async_session_factory() as session:
        await seed_admin(session)
        await session.commit()
    print("[init] admin account ready")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001 - surface any bootstrap failure
        print("[init] FAILED: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
