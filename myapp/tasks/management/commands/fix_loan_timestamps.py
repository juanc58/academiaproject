from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from tasks.models import Prestamo


class Command(BaseCommand):
    help = 'Backfill approved_at and returned_at for existing Prestamo rows. By default does a dry-run.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply the changes (default is dry-run).')
        parser.add_argument('--use-now', action='store_true', help='For remaining nulls, set timestamps to now (only when --apply).')

    def handle(self, *args, **options):
        apply_changes = options.get('apply', False)
        use_now = options.get('use_now', False)

        table = Prestamo._meta.db_table

        # inspect table columns
        with connection.cursor() as cursor:
            try:
                cols = [c.name for c in connection.introspection.get_table_description(cursor, table)]
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error inspecting table {table}: {e}'))
                return

        has_created = 'created_at' in cols
        has_approved = 'approved_at' in cols
        has_returned = 'returned_at' in cols

        self.stdout.write(f'Table: {table}')
        self.stdout.write(f'Columns found: {", ".join(cols)}')
        self.stdout.write(f'Has created_at: {has_created}; has approved_at: {has_approved}; has returned_at: {has_returned}')

        missing_approved_qs = Prestamo.objects.filter(approved_at__isnull=True)
        missing_approved_count = missing_approved_qs.count()
        missing_returned_qs = Prestamo.objects.filter(status=Prestamo.STATUS_RETURNED, returned_at__isnull=True)
        missing_returned_count = missing_returned_qs.count()

        self.stdout.write(f'Prestamos with approved_at NULL: {missing_approved_count}')
        self.stdout.write(f'Prestamos with status=returned and returned_at NULL: {missing_returned_count}')

        if not apply_changes:
            self.stdout.write(self.style.WARNING('Dry-run mode (no changes will be made). Use --apply to perform updates.'))

        # If DB has created_at column, prefer to copy created_at -> approved_at
        if has_created and has_approved:
            # compute count that would be updated
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f"SELECT COUNT(1) FROM {table} WHERE approved_at IS NULL AND created_at IS NOT NULL")
                    to_update = cursor.fetchone()[0]
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error counting rows for created_at -> approved_at: {e}'))
                    to_update = 0

            self.stdout.write(f'Rows to set approved_at = created_at: {to_update}')
            if apply_changes and to_update:
                self.stdout.write('Applying approved_at = created_at...')
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(f"UPDATE {table} SET approved_at = created_at WHERE approved_at IS NULL AND created_at IS NOT NULL")
                    self.stdout.write(self.style.SUCCESS('approved_at backfilled from created_at.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error applying approved_at backfill: {e}'))

        else:
            self.stdout.write('No created_at column available to copy from. Skipping created_at -> approved_at step.')

        # If there are returned loans missing returned_at but have approved_at, copy approved_at -> returned_at
        if has_approved and has_returned:
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f"SELECT COUNT(1) FROM {table} WHERE status = %s AND returned_at IS NULL AND approved_at IS NOT NULL", [Prestamo.STATUS_RETURNED])
                    to_update_ret = cursor.fetchone()[0]
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error counting rows for approved_at -> returned_at: {e}'))
                    to_update_ret = 0

            self.stdout.write(f'Rows to set returned_at = approved_at for returned loans: {to_update_ret}')
            if apply_changes and to_update_ret:
                self.stdout.write('Applying returned_at = approved_at for returned loans...')
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(f"UPDATE {table} SET returned_at = approved_at WHERE status = %s AND returned_at IS NULL AND approved_at IS NOT NULL", [Prestamo.STATUS_RETURNED])
                    self.stdout.write(self.style.SUCCESS('returned_at backfilled from approved_at for returned loans.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error applying returned_at backfill: {e}'))
        else:
            self.stdout.write('Skipping approved->returned copy because approved_at or returned_at column is missing.')

        # For any remaining approved_at NULL, optionally set to now
        remaining_after = Prestamo.objects.filter(approved_at__isnull=True).count()
        self.stdout.write(f'Remaining Prestamos with approved_at NULL after above steps: {remaining_after}')
        if apply_changes and use_now and remaining_after:
            self.stdout.write('Setting remaining approved_at to now()...')
            now = timezone.now()
            try:
                with transaction.atomic():
                    # update in ORM to ensure model fields handled properly
                    for loan in Prestamo.objects.filter(approved_at__isnull=True):
                        loan.approved_at = now
                        loan.save(update_fields=['approved_at'])
                self.stdout.write(self.style.SUCCESS(f'Set approved_at=now() for {remaining_after} rows.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error setting approved_at to now: {e}'))

        # For any returned loans still missing returned_at, optionally set from approved_at or now
        remaining_returned_after = Prestamo.objects.filter(status=Prestamo.STATUS_RETURNED, returned_at__isnull=True).count()
        self.stdout.write(f'Remaining returned loans without returned_at after above steps: {remaining_returned_after}')
        if apply_changes and remaining_returned_after:
            self.stdout.write('Attempting to set returned_at for remaining returned loans (from approved_at if available, else now if --use-now).')
            try:
                with transaction.atomic():
                    qs = Prestamo.objects.filter(status=Prestamo.STATUS_RETURNED, returned_at__isnull=True)
                    for loan in qs:
                        if loan.approved_at:
                            loan.returned_at = loan.approved_at
                        elif use_now:
                            loan.returned_at = timezone.now()
                        else:
                            self.stdout.write(self.style.NOTICE(f'Skipping loan id={loan.id} (no approved_at and --use-now not set)'))
                            continue
                        loan.save(update_fields=['returned_at'])
                self.stdout.write(self.style.SUCCESS('Finished setting returned_at for remaining returned loans.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error setting returned_at for remaining loans: {e}'))

        self.stdout.write(self.style.SUCCESS('fix_loan_timestamps completed.'))
