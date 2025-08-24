import pathlib

FORMS = pathlib.Path("sales/forms.py")
txt = FORMS.read_text(encoding="utf-8")

if "LineFormSetFactory" in txt and "LineFormSet =" not in txt:
    txt += "\n\n# Alias untuk kompatibilitas lama\nLineFormSet = LineFormSetFactory()\n"
    FORMS.write_text(txt, encoding="utf-8")
    print("✓ Ditambahkan alias LineFormSet = LineFormSetFactory() di forms.py")
else:
    print("✓ Sudah ada atau tidak perlu diubah")
