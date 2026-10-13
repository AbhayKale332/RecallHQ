import argparse
import json
from pathlib import Path

from recallhq.db import migrate


def main() -> None:
    parser = argparse.ArgumentParser(prog="recallhq")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate")
    ingest_command = subcommands.add_parser("ingest")
    ingest_command.add_argument("path", type=Path)
    manifest_command = subcommands.add_parser("slack-manifest")
    manifest_command.add_argument("--base-url", required=True)
    subcommands.add_parser("slack-worker")
    init_command = subcommands.add_parser("slack-init")
    init_command.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        print("Migrations applied")
    elif args.command == "ingest":
        from recallhq.ingestion.pipeline import ingest
        report = ingest(args.path)
        print(f"Ingested {report['messages']} messages; {report['message_chunks']} message chunks; "
              f"{report['thread_chunks']} thread chunks ({report['thread_splits']} splits); "
              f"{report['embedded_chunks']} embedded with {report['embedding_model']}")
    elif args.command == "slack-manifest":
        from recallhq.slack.manifest import manifest
        print(json.dumps(manifest(args.base_url), indent=2))
    elif args.command == "slack-worker":
        from recallhq.slack.worker import run
        run()
    elif args.command == "slack-init":
        from cryptography.fernet import Fernet
        from dotenv import dotenv_values, set_key

        from recallhq.slack.manifest import manifest
        manifest(args.base_url)
        env = Path(".env.slack")
        env.touch(mode=0o600, exist_ok=True)
        values = dotenv_values(env)
        if not values.get("SLACK_ENCRYPTION_KEY"):
            set_key(env, "SLACK_ENCRYPTION_KEY", Fernet.generate_key().decode())
        set_key(env, "SLACK_PUBLIC_URL", args.base_url.rstrip("/"))
        env.chmod(0o600)
        print("Updated .env.slack with the public URL and installation encryption key.")


if __name__ == "__main__":
    main()
