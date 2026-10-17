"""DB tests run against the LOCAL Supabase started from task-queue/ (Docker).
Refuses any non-local database: these tests create and delete auth users."""
import os
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg.types.json import Jsonb

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
TEST_DOMAIN = "platform-test.local"


@pytest.fixture(scope="session")
def db_url():
    url = os.environ.get("PLATFORM_TEST_DATABASE_URL", LOCAL_DB)
    if urlparse(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.exit("PLATFORM_TEST_DATABASE_URL must be the local `supabase start` DB", returncode=2)
    try:
        psycopg.connect(url, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.exit("local Supabase is not running: cd ../task-queue && supabase start", returncode=2)
    from scripts.apply_platform_migrations import apply_migrations
    with psycopg.connect(url, autocommit=True) as c:
        apply_migrations(c)
    return url


@pytest.fixture()
def conn(db_url):
    with psycopg.connect(db_url, autocommit=True) as c:
        yield c
        c.execute("delete from auth.users where email like %s", (f"%@{TEST_DOMAIN}",))


@pytest.fixture()
def make_user(conn):
    def make(name: str, meta: dict | None = None) -> str:
        return conn.execute(
            "insert into auth.users (id, aud, role, email, raw_user_meta_data, created_at, updated_at) "
            "values (gen_random_uuid(), 'authenticated', 'authenticated', %s, %s, now(), now()) "
            "returning id::text", (f"{name}@{TEST_DOMAIN}", Jsonb(meta or {}))).fetchone()[0]
    return make
