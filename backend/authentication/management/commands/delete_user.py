from django.core.management.base import BaseCommand
from authentication.deletion_service import delete_user_account_and_memories


class Command(BaseCommand):
    help = "Permanently deletes a user account and wipes all their Neo4j graph memories and PostgreSQL rows."

    def add_arguments(self, parser):
        parser.add_argument("identifier", type=str, help="User ID, email, or username to delete")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation prompt",
        )

    def handle(self, *args, **options):
        ident = options["identifier"]
        skip_confirm = options.get("yes", False)

        if not skip_confirm:
            confirm = input(
                f"Are you sure you want to PERMANENTLY ERASE user '{ident}' and ALL graph memories? (y/N): "
            )
            if confirm.lower() != "y":
                self.stdout.write(self.style.WARNING("Deletion aborted."))
                return

        try:
            report = delete_user_account_and_memories(ident)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted user '{ident}'.\n"
                    f"Report:\n"
                    f"  Postgres: {report.get('postgres')}\n"
                    f"  Neo4j: {report.get('neo4j')}"
                )
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Failed to delete user '{ident}': {exc}"))
