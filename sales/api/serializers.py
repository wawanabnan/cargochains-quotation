# sales/api/serializers.py
from typing import List, Dict, Any
from django.db import transaction
from rest_framework import serializers
from sales.models import Quotation, Cargo, CargoCharge


# -----------------------------
# Leaf: CargoCharge
# -----------------------------
class CargoChargeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CargoCharge
        fields = [
            "id", "cargo", "charge_type", "description", "unit",
            "qty", "rate", "currency", "amount",
        ]
        read_only_fields = ["amount", "cargo"]  # cargo diisi otomatis saat nested create


# -----------------------------
# Middle: Cargo (with nested charges)
# -----------------------------
class CargoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    # nested
    charges = CargoChargeSerializer(many=True, required=False)

    class Meta:
        model = Cargo
        fields = [
            "id", "quotation", "description", "package_type", "qty",
            "weight_kg", "volume_cbm", "origin", "destination",
            "extra_notes", "charges",
        ]
        read_only_fields = ["quotation"]  # diisi otomatis saat nested create

    def validate(self, attrs):
        # Contoh validasi ringan: origin & destination wajib ada saat create
        if self.instance is None:
            if not attrs.get("origin") or not attrs.get("destination"):
                raise serializers.ValidationError("Origin dan Destination wajib diisi untuk setiap cargo.")
        return attrs

    def _upsert_charges(self, cargo: Cargo, charges_data: List[Dict[str, Any]]):
        """
        Upsert daftar charges:
        - Jika ada 'id' → update baris tersebut.
        - Jika tidak ada 'id' → create baru.
        - Baris yang tidak dikirim lagi → dihapus.
        """
        existing = {c.id: c for c in cargo.charges.all()}
        sent_ids = set()

        for ch in charges_data:
            ch_id = ch.pop("id", None)
            if ch_id and ch_id in existing:
                # update
                obj = existing[ch_id]
                for k, v in ch.items():
                    setattr(obj, k, v)
                obj.cargo = cargo
                obj.save()
                sent_ids.add(ch_id)
            else:
                # create
                CargoCharge.objects.create(cargo=cargo, **ch)

        # hapus yang tidak dikirim
        to_delete = [obj for cid, obj in existing.items() if cid not in sent_ids]
        for obj in to_delete:
            obj.delete()

    def create(self, validated_data):
        charges_data = validated_data.pop("charges", [])
        cargo = Cargo.objects.create(**validated_data)
        if charges_data:
            self._upsert_charges(cargo, charges_data)
        return cargo

    def update(self, instance: Cargo, validated_data):
        charges_data = validated_data.pop("charges", None)

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        if charges_data is not None:
            self._upsert_charges(instance, charges_data)

        return instance


# -----------------------------
# Root: Quotation (with nested cargos)
# -----------------------------
class QuotationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    cargos = CargoSerializer(many=True, required=False)

    class Meta:
        model = Quotation
        fields = [
            "id", "number", "date", "customer",
            "validity_date", "payment_terms", "notes",
            "cargos",
        ]
        read_only_fields = ["number"]  # di-generate otomatis di model.save()

    def validate(self, attrs):
        # contoh aturan bisnis sederhana saat create
        if self.instance is None:
            cargos_data = self.initial_data.get("cargos", [])
            if not cargos_data:
                raise serializers.ValidationError("Minimal harus ada 1 cargo di quotation.")
            # boleh tambahkan cek: setiap cargo minimal 1 charge, jika mau strict
        return attrs

    def _upsert_cargos(self, quotation: Quotation, cargos_data: List[Dict[str, Any]]):
        """
        Upsert daftar cargos beserta nested charges-nya.
        - 'id' ada → update cargo + sinkron charges
        - 'id' kosong → create cargo baru
        - cargo existing yang tidak dikirim → dihapus
        """
        existing = {c.id: c for c in quotation.cargos.all()}
        sent_ids = set()

        for cg in cargos_data:
            charges = cg.pop("charges", [])
            cargo_id = cg.pop("id", None)

            if cargo_id and cargo_id in existing:
                cargo_obj = existing[cargo_id]
                # update cargo
                for k, v in cg.items():
                    setattr(cargo_obj, k, v)
                cargo_obj.quotation = quotation
                cargo_obj.save()
                # upsert charges
                CargoSerializer()._upsert_charges(cargo_obj, charges)
                sent_ids.add(cargo_id)
            else:
                # create cargo baru
                cargo_obj = Cargo.objects.create(quotation=quotation, **cg)
                if charges:
                    CargoSerializer()._upsert_charges(cargo_obj, charges)

        # hapus cargo yang tidak dikirim
        to_delete = [obj for cid, obj in existing.items() if cid not in sent_ids]
        for obj in to_delete:
            obj.delete()

    @transaction.atomic
    def create(self, validated_data):
        cargos_data = validated_data.pop("cargos", [])
        quotation = Quotation.objects.create(**validated_data)
        if cargos_data:
            # inject FK
            for c in cargos_data:
                c["quotation"] = quotation.id  # tidak dipakai langsung, hanya agar jelas
            self._upsert_cargos(quotation, cargos_data)
        return quotation

    @transaction.atomic
    def update(self, instance: Quotation, validated_data):
        cargos_data = validated_data.pop("cargos", None)

        # update header
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        # sinkron cargos bila dikirim
        if cargos_data is not None:
            self._upsert_cargos(instance, cargos_data)

        return instance
