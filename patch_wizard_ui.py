from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "sales" / "templates" / "sales" / "quotation_wizard.html"
assert TPL.exists(), f"Tidak menemukan template: {TPL}"

def backup(p: Path):
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"• backup -> {b.name}")

print("== Patch Wizard UI (Transport Mode, Service Option, Multi Destination, Destination Header) ==")
backup(TPL)
html = TPL.read_text(encoding="utf-8")
changed = False

# 1) Sisipkan blok header form (Transport Mode, Service Option, Multi Destination, Destination Header)
if ("Transport Mode" not in html) or ("id_transport_mode" not in html):
    # cari area 'HEADER FORM START' atau blok header_row pertama
    insert_block = (
        '\n<div class="row g-3">\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Transport Mode</label>\n'
        '    {{ header_form.transport_mode }}\n'
        '  </div>\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Service Option</label>\n'
        '    {{ header_form.service_option }}\n'
        '    <div class="form-text">Wajib jika mode ≠ MULTI.</div>\n'
        '  </div>\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Multi Destination?</label><br>\n'
        '    {{ header_form.multi_destination }}\n'
        '  </div>\n'
        '  <div class="col-md-3" id="dest-header-wrap">\n'
        '    <label class="form-label">Destination (Header)</label>\n'
        '    {{ header_form.destination_header }}\n'
        '  </div>\n'
        '</div>\n'
    )

    if "<!-- HEADER FORM START -->" in html:
        html = html.replace("<!-- HEADER FORM START -->", "<!-- HEADER FORM START -->" + insert_block)
        changed = True
        print("✓ Disisipkan blok UI setelah <!-- HEADER FORM START -->")
    else:
        # fallback: selipkan setelah baris yang memuat {{ header_form.notes }} bila ada
        if "{{ header_form.notes }}" in html:
            html = html.replace("{{ header_form.notes }}", "{{ header_form.notes }}\n" + insert_block)
            changed = True
            print("✓ Disisipkan blok UI setelah header_form.notes")
        else:
            # fallback terakhir: selipkan setelah <form ...> pertama
            html = re.sub(r"(<form[^>]*>)", r"\1\n" + insert_block, html, count=1)
            changed = True
            print("✓ Disisipkan blok UI setelah tag <form> pertama")

# 2) Tandai kolom destination pada cargo lines agar bisa di-hide via JS
dest_marked = False
# Pola <td> {{ f.destination }} </td> atau varian spacing
pattern_td_dest = re.compile(r"(<td[^>]*>)(\s*\{\{\s*f\.destination\s*\}\}\s*)(</td>)", flags=re.IGNORECASE)
if pattern_td_dest.search(html):
    html = pattern_td_dest.sub(r'<td data-cargo-destination>\2</td>', html)
    dest_marked = True
    changed = True
    print("✓ Kolom destination cargo diberi marker data-cargo-destination")

# 3) Tambah JS dinamis bila belum ada (service options per mode + hide destination saat single)
if "applyWizardFlags()" not in html:
    html += """
<script>
  // Service options per mode
  const SERVICE_BY_MODE = {
    'SEA': [
      {v:'D2D', t:'Door → Door'},
      {v:'D2P', t:'Door → Port'},
      {v:'P2P', t:'Port → Port'}
    ],
    'AIR': [
      {v:'A2A', t:'Airport → Airport'},
      {v:'D2A', t:'Door → Airport'}
    ],
    'LAND': [
      {v:'D2D', t:'Door → Door'},
      {v:'H2H', t:'Hub → Hub'}
    ],
    'MULTI': []
  };

  function fillServiceOptions(mode){
    const sel = document.getElementById('id_service_option');
    if(!sel) return;
    const current = sel.value;
    sel.innerHTML = '';
    (SERVICE_BY_MODE[mode] || []).forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.v; o.textContent = opt.t;
      sel.appendChild(o);
    });
    if(mode === 'MULTI'){
      const o = document.createElement('option');
      o.value = ''; o.textContent = '— (Not required)';
      sel.appendChild(o);
      sel.value = '';
    }else{
      if(!Array.from(sel.options).some(x=>x.value===current)){
        if(sel.options.length) sel.selectedIndex = 0;
      }else{
        sel.value = current;
      }
    }
  }

  function applyWizardFlags(){
    const modeSel = document.getElementById('id_transport_mode');
    const multiChk = document.getElementById('id_multi_destination');
    const destHeader = document.getElementById('id_destination_header');
    const destWrap = document.getElementById('dest-header-wrap');

    const mode = modeSel ? modeSel.value : 'MULTI';
    const multi = multiChk ? multiChk.checked : true;

    fillServiceOptions(mode);

    // show/hide Destination (Header)
    if(destWrap) destWrap.style.display = multi ? 'none' : '';

    // hide/show destination inputs di cargo lines (saat single)
    const tds = document.querySelectorAll('[data-cargo-destination]');
    tds.forEach(td=>{
      td.style.display = multi ? '' : 'none';
      if(!multi && destHeader){
        const input = td.querySelector('input,select,textarea');
        if(input) input.value = destHeader.value;
      }
    });
  }

  document.addEventListener('change', (e)=>{
    if(['id_transport_mode','id_multi_destination','id_destination_header'].includes(e.target.id)){
      applyWizardFlags();
    }
  });
  document.addEventListener('DOMContentLoaded', applyWizardFlags);
</script>
"""
    changed = True
    print("✓ Ditambahkan JS applyWizardFlags() untuk dinamis UI")

if changed:
    TPL.write_text(html, encoding="utf-8")
    print(f"\nSelesai ✅  File diperbarui: {TPL.name}")
    if not dest_marked:
        print("Catatan: Tidak menemukan cell <td>{{ f.destination }}</td>. Pastikan nama fieldnya 'destination'.")
else:
    print("• Tidak ada perubahan. Mungkin patch sudah pernah diterapkan atau struktur file berbeda.")

print("\nLangkah selanjutnya:")
print(" - Pastikan model Quotation & QuotationForm sudah punya field: transport_mode, service_option, multi_destination, destination_header.")
print(" - Restart server bila perlu.")
