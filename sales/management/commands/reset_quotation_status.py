from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from sales.models import FreightQuotation

import sys
from datetime import datetime

class Command(BaseCommand):
    help = "Reset / set ulang status FreightQuotation (by ids / all / filter)."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Target status (wajib). Contoh: DRAFT/SENT/CONFIRMED/CLOSED/CANCELLED")
        parser.add_argument("--ids", help="Comma-separated quotation IDs. Contoh: 1,2,3")
        parser.add_argument("--from-status", dest="from_status", help="Filter hanya yang status awal = ini")
        parser.add_argument("--date-from", help="Filter tanggal minimal (YYYY-MM-DD), cocokkan ke field `date`")
        parser.add_argument("--date-to", help="Filter tanggal maksimal (YYYY-MM-DD), cocokkan ke field `date`")
        parser.add_argument("--all", action="store_true", help="Terapkan ke semua data (hormati filter lain jika diberikan)")
        parser.add_argument("--dry-run", action="store_true", help="Tampilkan rencana perubahan tanpa menulis ke DB")
        parser.add_argument("--force", action="store_true", help="Izinkan mengubah CLOSED/CANCELLED")

    def handle(self, *args, **opts):
        target = (opts.get("to") or "").upper().strip()
        valid_status = {s for s, _ in FreightQuotation.STATUS_CHOICES}

        if target not in valid_status:
            raise CommandError(f"Status target tidak valid: {target}. Pilihan: {sorted(valid_status)}")

        ids_str = (opts.get("ids") or "").strip()
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]

        from_status = (opts.get("from_status") or "").upper().strip()
        if from_status and from_status not in valid_status:
            raise CommandError(f"from-status tidak valid: {from_status}. Pilihan: {sorted(valid_status)}")

        date_from = opts.get("date_from")
        date_to = opts.get("date_to")
        use_all = bool(opts.get("all"))
        dry_run = bool(opts.get("dry_run"))
        force = bool(opts.get("force"))

        if not use_all and not ids:
            raise CommandError("Tentukan --all atau --ids=…")

        qs = FreightQuotation.objects.all()

        if ids:
            qs = qs.filter(id__in=ids)

        if from_status:
            qs = qs.filter(status=from_status)

        # filter tanggal berdasarkan field model `date`
        def _parse(d):
            try:
                return datetime.strptime(d, "%Y-%m-%d").date()
            except Exception:
                raise CommandError(f"Format tanggal salah: {d} (pakai YYYY-MM-DD)")

        if date_from:
            qs = qs.filter(date__gte=_parse(date_from))
        if date_to:
            qs = qs.filter(date__lte=_parse(date_to))

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("Tidak ada data yang cocok dengan filter."))
            return

        # aturan: protect CLOSED / CANCELLED kecuali --force
        protected = Q(status__in=["CLOSED", "CANCELLED"])
        if not force:
            qs_updatable = qs.exclude(protected)
        else:
            qs_updatable = qs

        will_update = qs_updatable.exclude(status=target)  # tak perlu update kalau sudah sama
        n_update = will_update.count()
        n_skip_same = qs_updatable.filter(status=target).count()
        n_blocked = total - qs_updatable.count()

        self.stdout.write(f"Total match     : {total}")
        self.stdout.write(f"  - Akan diubah : {n_update}")
        self.stdout.write(f"  - Sudah sama  : {n_skip_same}")
        self.stdout.write(f"  - Terlindungi : {n_blocked}{' (pakai --force untuk override)' if n_blocked and not force else ''}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN aktif: tidak ada data diubah."))
            return

        updated = 0
        for q in will_update.iterator():
            q.status = target
            q.save(update_fields=["status"])
            updated += 1

        updated = will_update.update(status=target)
        self.stdout.write(self.style.SUCCESS(f"Selesai. Berhasil ubah {updated} quotation ke status {target}."))
