import argparse
from pathlib import Path

from recallhq.db import migrate
from recallhq.ingestion.pipeline import ingest


def main() -> None:
    parser = argparse.ArgumentParser(prog="recallhq")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate")
    ingest_command = subcommands.add_parser("ingest")
    ingest_command.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        print("Migrations applied")
    elif args.command == "ingest":
        report = ingest(args.path)
        print(f"Ingested {report['messages']} messages; {report['message_chunks']} message chunks; "
              f"{report['thread_chunks']} thread chunks ({report['thread_splits']} splits); "
              f"{report['embedded_chunks']} embedded with {report['embedding_model']}")


if __name__ == "__main__":
    main()
