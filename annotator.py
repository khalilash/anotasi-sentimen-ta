"""
UI anotasi aspek sentimen (Streamlit) yang menulis langsung ke Google Sheet.
Menggunakan OAuth login (tanpa file credentials.json).
"""
import html
import gspread
import streamlit as st

SHEET_ID = "1nSD0S32aQUcppihT1cizeY5Txl9yFmxaUHv6yX7k8tc"
WS_NAME = "Anotasi"

ASPEK = ["Pengobatan", "Gejala & Diagnosis", "Penularan & Kebersihan", "Pantangan Makanan"]
OPSI = ["Positif", "Negatif", "Netral", "Tidak Ada"]
IDX_TIDAK_ADA = 3

C_ID, C_KONTEKS, C_KOMENTAR, C_ASPEK0, C_CATATAN = 0, 1, 2, 3, 19
N_COL = 21

st.set_page_config(page_title="Anotasi Sentimen", layout="centered")

@st.cache_resource
def get_ws():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(SHEET_ID).worksheet(WS_NAME)

def parse_labels(row):
    labels = []
    for a in range(len(ASPEK)):
        seg = row[C_ASPEK0 + 4 * a : C_ASPEK0 + 4 * a + 4]
        picked = [i for i, v in enumerate(seg) if str(v).strip() in ("1", "1.0")]
        labels.append(picked[0] if len(picked) == 1 else None)
    return labels

def load_rows():
    raw = get_ws().get_all_values()
    rows = []
    for i, r in enumerate(raw[2:], start=3):
        r = r + [""] * (N_COL - len(r))
        if not r[C_ID].strip() and not r[C_KOMENTAR].strip():
            continue
        rows.append({
            "sheet_row": i,
            "id": r[C_ID],
            "konteks": r[C_KONTEKS],
            "komentar": r[C_KOMENTAR],
            "labels": parse_labels(r),
            "catatan": r[C_CATATAN],
        })
    return rows

def save(item, labels, catatan):
    vals = []
    for a in range(len(ASPEK)):
        for o in range(len(OPSI)):
            vals.append(1 if labels[a] == o else "")
    vals.append(catatan)
    r = item["sheet_row"]
    get_ws().update(range_name=f"D{r}:T{r}", values=[vals], value_input_option="USER_ENTERED")
    item["labels"] = list(labels)
    item["catatan"] = catatan

if "rows" not in st.session_state:
    with st.spinner("Memuat sheet..."):
        st.session_state.rows = load_rows()
    rows = st.session_state.rows
    st.session_state.pos = next((i for i, it in enumerate(rows) if None in it["labels"]), len(rows))

rows = st.session_state.rows
pos = st.session_state.pos
total = len(rows)
done = sum(1 for it in rows if None not in it["labels"])

st.progress(done / total if total else 0.0, text=f"{done} / {total} komentar sudah dilabeli")

with st.sidebar:
    st.header("Ringkasan pedoman")
    st.markdown(
        "- **Pengobatan**: obat, salep, sabun, ramuan, herbal, cara pengobatan lain.\n"
        "- **Gejala & Diagnosis**: keluhan kulit, ciri penyakit, dugaan/diagnosis, rujukan dokter.\n"
        "- **Penularan & Kebersihan**: cara menular, cuci/jemur baju dan kasur, kebersihan lingkungan.\n"
        "- **Pantangan Makanan**: makanan yang dianjurkan atau dilarang.\n\n"
        "**Sentimen**: Positif = dinilai baik/berhasil. Negatif = dinilai buruk/bermasalah. "
        "Netral = disebut tanpa penilaian. Tidak Ada = tidak disinggung.\n\n"
        "**Kasus khusus**: pertanyaan murni = Netral di aspek yang ditanya. "
        "Doa/dukungan = semua Tidak Ada. Iklan = centang SPAM."
    )
    if st.button("Muat ulang dari sheet"):
        st.session_state.clear()
        st.rerun()

if pos >= total:
    st.success("Semua komentar sudah dilabeli. Cek kolom Cek di sheet harus OK semua.")
    if total and st.button("⬅ Kembali ke komentar terakhir"):
        st.session_state.pos = total - 1
        st.rerun()
    st.stop()

item = rows[pos]
st.caption(f"Komentar {pos + 1} dari {total}  |  id {item['id']}  |  baris sheet {item['sheet_row']}")

with st.container(border=True):
    st.markdown("**Konteks postingan**")
    konteks_teks = html.escape(item['konteks']) if item['konteks'] else '<i>(kosong)</i>'
    st.markdown(f"<div style='opacity:.85'>{konteks_teks}</div>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("**Komentar**")
    komentar_teks = html.escape(item['komentar']) if item['komentar'] else '<i>(kosong)</i>'
    st.markdown(f"<div style='font-size:1.1rem'>{komentar_teks}</div>", unsafe_allow_html=True)

is_spam = st.checkbox("SPAM (iklan/promosi)", value=(item["catatan"].strip() == "SPAM"), key=f"spam_{pos}")

labels = []
if is_spam:
    labels = [IDX_TIDAK_ADA] * len(ASPEK)
    st.info("Mode SPAM: semua aspek otomatis Tidak Ada, Catatan terisi SPAM.")
else:
    for a, nama in enumerate(ASPEK):
        choice = st.radio(
            nama,
            OPSI,
            index=item["labels"][a],
            horizontal=True,
            key=f"asp{a}_{pos}",
        )
        labels.append(OPSI.index(choice) if choice else None)

default_note = "" if item["catatan"].strip() == "SPAM" else item["catatan"]
catatan = "SPAM" if is_spam else st.text_input("Catatan (opsional, isi kalau ragu)", value=default_note, key=f"cat_{pos}")

ready = None not in labels
c1, c2 = st.columns(2)
with c1:
    if st.button("⬅ Back", disabled=pos == 0, use_container_width=True):
        st.session_state.pos -= 1
        st.rerun()
with c2:
    if st.button("Next ➜", type="primary", disabled=not ready, use_container_width=True):
        with st.spinner("Menyimpan ke sheet..."):
            save(item, labels, catatan)
        st.session_state.pos += 1
        st.rerun()