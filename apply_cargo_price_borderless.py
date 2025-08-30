# apply_cargo_price_borderless.py
from pathlib import Path
import shutil, textwrap, datetime, re

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
APP = ROOT / "sales"
TPL = ROOT / "templates" / "sales" / "freight"

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

# 1) MODELS: tambah price di FreightCargo
def patch_models():
    p = APP / "models.py"
    txt = p.read_text(encoding="utf-8")
    backup(p)

    # Tambah kolom price jika belum ada
    if "class FreightCargo" in txt and " price =" not in txt:
        txt = re.sub(
            r"(class\s+FreightCargo\(models\.Model\):(.*?\n))(.*?amount\s*=\s*models\.DecimalField[^\n]*\n)",
            r"\1\3    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)\n",
            txt, flags=re.S
        )
        p.write_text(txt, encoding="utf-8")
        print("[patched] sales/models.py (add FreightCargo.price)")
    else:
        print("[skip] models already has price or class not found")

# 2) FORMS: borderless widgets + qty default 1 + tambah price field
def patch_forms():
    p = APP / "forms.py"
    txt = p.read_text(encoding="utf-8")
    backup(p)

    # Borderless CSS helper
    BORDERLESS = 'class": "form-control form-control-sm border-0 bg-transparent p-0'
    BORDERLESS_NUM = 'class": "form-control form-control-sm border-0 bg-transparent p-0 text-end'

    # Tambah field price di FreightCargoForm
    txt = re.sub(
        r"class\s+FreightCargoForm\(forms\.ModelForm\):(.*?)(\nclass\s|\Z)",
        lambda m: (
            m.group(0)
            if " price" in m.group(0)
            else m.group(0).replace(
                "class Meta:",
                'price = forms.DecimalField(required=False, initial=0, widget=forms.NumberInput(attrs={"class":"form-control form-control-sm border-0 bg-transparent p-0 text-end"}))\n\n    class Meta:'
            )
        ),
        txt, flags=re.S
    )

    # Pastikan fields dalam Meta mencakup price
    txt = re.sub(
        r"(class Meta:\s*?\n\s*model\s*=\s*FreightCargo\s*?\n\s*fields\s*=\s*\[)([^\]]*)(\])",
        lambda m: m.group(1) + (
            "description\",\"qty\",\"weight_kg\",\"volume_cbm\",\"price\",\"amount\",\"origin\",\"destination\""
            if "price" not in m.group(2) else m.group(2)
        ) + m.group(3),
        txt, flags=re.S
    )

    # Borderless widgets Cargo
    txt = re.sub(r'"description":\s*forms\.TextInput\([^\)]*\)',
                 f'"description": forms.TextInput(attrs{{"{BORDERLESS}}})'.replace("{", "{").replace("}", "}"),
                 txt)
    for fld in ["qty","weight_kg","volume_cbm","amount"]:
        txt = re.sub(
            rf'"{fld}":\s*forms\.NumberInput\([^\)]*\)',
            f'"{fld}": forms.NumberInput(attrs{{"{BORDERLESS_NUM}}})'.replace("{", "{").replace("}", "}"),
            txt
        )
    # Borderless widgets Origin/Destination selects
    txt = re.sub(
        r'forms\.Select\(attrs=\{[^\}]*\}\)',
        'forms.Select(attrs={"class":"form-select form-select-sm border-0 bg-transparent p-0"})',
        txt
    )

    # qty initial=1 di Cargo & Charge
    txt = re.sub(
        r'(class\s+FreightCargoForm\(forms\.ModelForm\):(.*?))class Meta:',
        r'\1def __init__(self,*args,**kwargs):\n        super().__init__(*args,**kwargs)\n        self.fields.get("qty") and self.fields["qty"].widget.attrs.update({"value":"1"})\n\n    class Meta:',
        txt, flags=re.S
    )
    txt = re.sub(
        r'(class\s+FreightChargeForm\(forms\.ModelForm\):(.*?))class Meta:',
        r'\1def __init__(self,*args,**kwargs):\n        super().__init__(*args,**kwargs)\n        self.fields.get("qty") and self.fields["qty"].widget.attrs.update({"value":"1"})\n\n    class Meta:',
        txt, flags=re.S
    )

    # Borderless widgets Charge
    txt = re.sub(
        r'class\s+FreightChargeForm\(forms\.ModelForm\):(.*?)(class\s+Meta:)',
        lambda m: re.sub(
            r'"description":\s*forms\.TextInput\([^\)]*\)',
            f'"description": forms.TextInput(attrs{{"{BORDERLESS}}})'.replace("{", "{").replace("}", "}"),
            m.group(0)
        ),
        txt, flags=re.S
    )
    for fld in ["qty","rate","amount"]:
        txt = re.sub(
            rf'"{fld}":\s*forms\.NumberInput\([^\)]*\)',
            f'"{fld}": forms.NumberInput(attrs{{"{BORDERLESS_NUM}}})'.replace("{", "{").replace("}", "}"),
            txt
        )

    (APP / "forms.py").write_text(txt, encoding="utf-8")
    print("[patched] sales/forms.py (borderless + price + qty=1)")

# 3) VIEWS: auto-calc amount (cargo: qty*price; charge: qty*rate) bila kosong
def patch_views():
    p = APP / "views.py"
    txt = p.read_text(encoding="utf-8")
    backup(p)

    # Saat create FreightCargo, isi price & amount kalkulasi jika kosong
    txt = re.sub(
        r"FreightCargo\.objects\.create\(\s*quotation=q,\s*description=cd\.get\(\"description\"\),\s*qty=cd\.get\(\"qty\"\)\s*or\s*0,\s*weight_kg=cd\.get\(\"weight_kg\"\)\s*or\s*0,\s*volume_cbm=cd\.get\(\"volume_cbm\"\)\s*or\s*0,\s*amount=cd\.get\(\"amount\"\)\s*or\s*0,\s*origin=cd\.get\(\"origin\"\),\s*destination=cd\.get\(\"destination\"\),\s*\)",
        "FreightCargo.objects.create(\n                        quotation=q,\n                        description=cd.get(\"description\"),\n                        qty=cd.get(\"qty\") or 1,\n                        weight_kg=cd.get(\"weight_kg\") or 0,\n                        volume_cbm=cd.get(\"volume_cbm\") or 0,\n                        price=cd.get(\"price\") or 0,\n                        amount=( (cd.get(\"qty\") or 1) * (cd.get(\"price\") or 0) ) if (cd.get(\"amount\") in [None, \"\", 0]) else cd.get(\"amount\"),\n                        origin=cd.get(\"origin\"),\n                        destination=cd.get(\"destination\"),\n                    )",
        txt, flags=re.S
    )

    # Saat create FreightCharge, auto amount = qty*rate bila kosong
    txt = re.sub(
        r"FreightCharge\.objects\.create\(\s*cargo=first_cargo,\s*description=cd\.get\(\"description\",\s*\"\"\),\s*qty=cd\.get\(\"qty\"\)\s*or\s*0,\s*rate=cd\.get\(\"rate\"\)\s*or\s*0,\s*amount=cd\.get\(\"amount\"\)\s*or\s*0,\s*\)",
        "FreightCharge.objects.create(\n                            cargo=first_cargo,\n                            description=cd.get(\"description\",\"\"),\n                            qty=cd.get(\"qty\") or 1,\n                            rate=cd.get(\"rate\") or 0,\n                            amount=( (cd.get(\"qty\") or 1) * (cd.get(\"rate\") or 0) ) if (cd.get(\"amount\") in [None, \"\", 0]) else cd.get(\"amount\"),\n                        )",
        txt, flags=re.S
    )

    p.write_text(txt, encoding="utf-8")
    print("[patched] sales/views.py (auto-calc amount)")

# 4) TEMPLATE: tambah kolom Price di Cargo + borderless sudah dari widget
def patch_template():
    p = TPL / "wizard.html"
    txt = p.read_text(encoding="utf-8")
    backup(p)

    # Tambah kolom header Price setelah Volume, sebelum Amount
    txt = txt.replace(
        '<th class="text-end" style="width:120px;">Volume (cbm)</th>\n                <th class="text-end" style="width:140px;">Amount</th>',
        '<th class="text-end" style="width:120px;">Volume (cbm)</th>\n                <th class="text-end" style="width:120px;">Price</th>\n                <th class="text-end" style="width:140px;">Amount</th>'
    )

    # Tambah cell f.price pada body
    txt = txt.replace(
        '{{ f.volume_cbm }} {{ f.volume_cbm.errors }}\n                </td>\n                <td class="text-end">\n                  {{ f.amount }} {{ f.amount.errors }}',
        '{{ f.volume_cbm }} {{ f.volume_cbm.errors }}\n                </td>\n                <td class="text-end">\n                  {{ f.price }} {{ f.price.errors }}\n                </td>\n                <td class="text-end">\n                  {{ f.amount }} {{ f.amount.errors }}'
    )

    # JS: auto-calc amount = qty*price (cargo) dan qty*rate (charge)
    js_snippet = """
    <script>
    (function(){
      function calcRowQtyPrice(row, qtyName, priceName, amountName){
        const q=row.querySelector(`[name$='-${qtyName}']`);
        const p=row.querySelector(`[name$='-${priceName}']`);
        const a=row.querySelector(`[name$='-${amountName}']`);
        if(!q||!p||!a) return;
        const qv=parseFloat(q.value||'1'); const pv=parseFloat(p.value||'0');
        a.value = ( (isNaN(qv)?1:qv) * (isNaN(pv)?0:pv) ).toFixed(2);
      }
      function bind(tableSel, qtyName, priceName, amountName){
        document.querySelectorAll(tableSel+' tbody tr').forEach(tr=>{
          const handler=()=>calcRowQtyPrice(tr, qtyName, priceName, amountName);
          tr.addEventListener('input', handler);
          handler();
        });
      }
      // Cargo: qty * price -> amount
      bind('.card-body table:nth-of-type(1)', 'qty','price','amount');
      // Charge: qty * rate -> amount
      bind('.card-body table:nth-of-type(2)', 'qty','rate','amount');
    })();
    </script>
    """
    # sisipkan sebelum {% endblock %} extra_js atau tambahkan ke akhir file
    if "{% endblock %}" in txt:
        txt = re.sub(r"(\{% endblock %}\s*)$", js_snippet + r"\1", txt, flags=re.S)
    else:
        txt += js_snippet

    p.write_text(txt, encoding="utf-8")
    print("[patched] templates/sales/freight/wizard.html (add Price + auto-calc)")
    

def main():
    patch_models()
    patch_forms()
    patch_views()
    patch_template()
    print("\n✅ Patch applied.")
    print("➡ Jalankan migrasi untuk kolom baru:")
    print("   python manage.py makemigrations sales && python manage.py migrate")
    print("➡ Buka: /sales/quotations/freight/new/?step=lines")
    print("   - Input terlihat borderless (via widget kelas Bootstrap).")
    print("   - Qty default 1; Amount auto = Qty × Price (Cargo) / Qty × Rate (Charge).")

if __name__ == "__main__":
    main()
