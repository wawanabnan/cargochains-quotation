# fix_formset_management.py
from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

# --- 1) Views: pastikan prefix konsisten untuk formset (GET & POST) ---
def patch_views():
    vp = ROOT / "sales" / "views.py"
    if not vp.exists():
        print("[skip] sales/views.py not found")
        return
    backup(vp)
    src = vp.read_text(encoding="utf-8")

    # Normalisasi tabs -> spaces
    src = src.replace("\t", "    ")

    # POST: CargoFS(request.POST, ...) -> selalu ada prefix="cargo"
    src = re.sub(
        r"CargoFS\(\s*request\.POST\s*(?:,\s*prefix\s*=\s*['\"]cargo['\"])?\s*\)",
        "CargoFS(request.POST, prefix=\"cargo\")",
        src,
    )
    # POST: ChargeFS(request.POST, ...) -> prefix="charge"
    src = re.sub(
        r"ChargeFS\(\s*request\.POST\s*(?:,\s*prefix\s*=\s*['\"]charge['\"])?\s*\)",
        "ChargeFS(request.POST, prefix=\"charge\")",
        src,
    )
    # GET: CargoFS(...) -> CargoFS(prefix="cargo")
    src = re.sub(
        r"CargoFS\(\s*\)",
        "CargoFS(prefix=\"cargo\")",
        src,
    )
    # GET: ChargeFS(...) -> ChargeFS(prefix="charge")
    src = re.sub(
        r"ChargeFS\(\s*\)",
        "ChargeFS(prefix=\"charge\")",
        src,
    )

    vp.write_text(src, encoding="utf-8")
    print("[patched] sales/views.py (formset prefixes normalized)")

# --- 2) Template: pastikan management_form kedua formset ada di dalam satu <form> ---
def patch_template():
    tp = ROOT / "templates" / "sales" / "freight" / "wizard.html"
    if not tp.exists():
        print("[skip] templates/sales/freight/wizard.html not found")
        return
    backup(tp)
    html = tp.read_text(encoding="utf-8")

    # Siapkan blok 'lines' yang benar (SATU form, dengan 2 management_form)
    LINES_BLOCK = """
    {% elif step == 'lines' %}
      <form method="post" novalidate>
        {% csrf_token %}

        {{ cargo_fs.management_form }}
        {{ charge_fs.management_form }}

        <h6 class="mb-2">Cargo Detail</h6>
        <div class="table-responsive mb-3">
          <table class="table table-sm align-middle">
            <thead class="table-light">
              <tr>
                <th>Description</th>
                <th class="text-end" style="width:100px;">Qty</th>
                <th class="text-end" style="width:120px;">Weight (kg)</th>
                <th class="text-end" style="width:120px;">Volume (cbm)</th>
                <th class="text-end" style="width:120px;">Price</th>
                <th class="text-end" style="width:140px;">Amount</th>
                <th style="width:220px;">Origin</th>
                <th style="width:220px;">Destination</th>
              </tr>
            </thead>
            <tbody>
              {% for f in cargo_fs %}
              <tr>
                <td>{{ f.description }} {{ f.description.errors }}</td>
                <td class="text-end">{{ f.qty }} {{ f.qty.errors }}</td>
                <td class="text-end">{{ f.weight_kg }} {{ f.weight_kg.errors }}</td>
                <td class="text-end">{{ f.volume_cbm }} {{ f.volume_cbm.errors }}</td>
                <td class="text-end">{{ f.price }} {{ f.price.errors }}</td>
                <td class="text-end">{{ f.amount }} {{ f.amount.errors }}</td>
                <td>{{ f.origin }} {{ f.origin.errors }}</td>
                <td>{{ f.destination }} {{ f.destination.errors }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>

        <h6 class="mb-2">Cargo Charge Lines <small class="text-muted">(optional)</small></h6>
        <div class="table-responsive">
          <table class="table table-sm align-middle">
            <thead class="table-light">
              <tr>
                <th>Charge</th>
                <th class="text-end" style="width:100px;">Qty</th>
                <th class="text-end" style="width:140px;">Rate</th>
                <th class="text-end" style="width:140px;">Amount</th>
              </tr>
            </thead>
            <tbody>
              {% for f in charge_fs %}
              <tr>
                <td>{{ f.description }} {{ f.description.errors }}</td>
                <td class="text-end">{{ f.qty }} {{ f.qty.errors }}</td>
                <td class="text-end">{{ f.rate }} {{ f.rate.errors }}</td>
                <td class="text-end">{{ f.amount }} {{ f.amount.errors }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>

        <div class="d-flex justify-content-between mt-3">
          <a href="?step=header" class="btn btn-outline-secondary rounded-0">Back</a>
          <button class="btn btn-primary rounded-0" type="submit">Create</button>
        </div>
      </form>
    {% endif %}
    """

    # Ganti seluruh blok lines lama dengan yang baru
    pattern = re.compile(r"\{\%\s*elif\s+step\s*==\s*'lines'\s*\%\}[\s\S]*?\{\%\s*endif\s*\%\}", re.M)
    if pattern.search(html):
        html2 = pattern.sub(textwrap.dedent(LINES_BLOCK).lstrip(), html)
    else:
        # kalau marker tidak ketemu, coba sisipkan setelah header-block
        html2 = html
        html2 += "\n" + textwrap.dedent(LINES_BLOCK).lstrip()

    tp.write_text(html2, encoding="utf-8")
    print("[patched] wizard.html (single <form> + management_form for both formsets)")

def main():
    patch_views()
    patch_template()
    print("\n✅ Done. Restart server, lalu uji submit step 'lines'.")
    print("Jika error masih muncul, kirim isi 10–15 baris sekitar block `{% elif step == 'lines' %}` di wizard.html.")

if __name__ == "__main__":
    main()
