"""
UI Evaluasi Prediksi Model & Pelabelan Ulang (Streamlit Cloud)
Mapping kolom: A=id, B=aspek, C=teks, D=konteks, E=prediksi, F=benar, G=label_seharusnya
"""
import html
import gspread
import streamlit as st

SHEET_ID = "1b37oxZ0dEOoBAmsVm-muM1TM5N9OClI7qBQwg3nZloU"
WS_NAME = "cek_batch1"  # Sesuaikan jika nama tab di bawah sheet berbeda

OPSI_BENAR = ["Ya", "Tidak"]
OPSI_LABEL = ["Positif", "Negatif", "Netral", "Tidak Ada"]

C_ID = 0
C_ASPEK = 1
C_TEKS = 2
C_KONTEKS = 3
C_PREDIKSI = 4
C_BENAR = 5
C_SEHARUSNYA = 6
N_COL = 7

st.set_page_config(page_title="Evaluasi Prediksi Sentimen", layout="centered")

@st.cache_resource
def get_ws():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(SHEET_ID).worksheet(WS_NAME)

def load_rows():
    raw = get_ws().get_all_values()
    rows = []
    for i, r in enumerate(raw[1:], start=2):
        r = r + [""] * (N_COL - len(r))
        if not r[C_TEKS].strip() and not r[C_ASPEK].strip():
            continue
        rows.append({
            "sheet_row": i,
            "id": r[C_ID],
            "aspek": r[C_ASPEK],
            "teks": r[C_TEKS],
            "konteks": r[C_KONTEKS],
            "prediksi": r[C_PREDIKSI].strip(),
            "benar": r[C_BENAR].strip(),
            "seharusnya": r[C_SEHARUSNYA].strip(),
        })
    return rows

def is_done(item):
    if item["seharusnya"].upper() == "SPAM":
        return True
    if item["benar"] == "Ya":
        return True
    if item["benar"] == "Tidak" and item["seharusnya"] in OPSI_LABEL:
        return True
    return False

def save_row(item, val_benar, val_seharusnya):
    r = item["sheet_row"]
    # Update kolom F (benar) dan G (label_seharusnya) sekaligus
    get_ws().update(
        range_name=f"F{r}:G{r}",
        values=[[val_benar, val_seharusnya]],
        value_input_option="USER_ENTERED"
    )
    item["benar"] = val_benar
    item["seharusnya"] = val_seharusnya

if "rows" not in st.session_state:
    with st.spinner("Memuat data sheet..."):
        st.session_state.rows = load_rows()
    rows = st.session_state.rows
    st.session_state.pos = next((i for i, it in enumerate(rows) if not is_done(it)), len(rows))

rows = st.session_state.rows
pos = st.session_state.pos

# Menghitung statistik (SPAM dikeluarkan dari hitungan evaluasi)
valid_rows = [it for it in rows if it["seharusnya"].upper() != "SPAM"]
spam_count = len(rows) - len(valid_rows)
done_valid = sum(1 for it in valid_rows if is_done(it))
total_valid = len(valid_rows)

st.progress(
    done_valid / total_valid if total_valid else 0.0,
    text=f"Evaluasi valid: {done_valid} / {total_valid} selesai  |  SPAM dikecualikan: {spam_count}"
)

with st.sidebar:
    st.header("Panduan Evaluasi")
    st.markdown(
        "- **SPAM**: Jika komentar jelas iklan/jualan/nomor WA, centang **Tandai sebagai SPAM**. Kolom `benar` otomatis dikosongkan, `label_seharusnya` terisi `SPAM`, dan baris dikeluarkan dari hitungan.\n"
        "- **Benar = Ya**: Jika prediksi model sudah sesuai dengan teks & aspek.\n"
        "- **Benar = Tidak**: Jika prediksi keliru, wajib pilih **Label Seharusnya** (`Positif`, `Negatif`, `Netral`, atau `Tidak Ada`)."
    )
    if st.button("Muat ulang dari sheet"):
        st.session_state.clear()
        st.rerun()

if pos >= len(rows):
    st.success("Semua baris data sudah selesai dievaluasi!")
    if rows and st.button("⬅ Kembali ke data terakhir"):
        st.session_state.pos = len(rows) - 1
        st.rerun()
    st.stop()

item = rows[pos]
st.caption(f"Baris ke-{pos + 1} dari {len(rows)} total baris  |  Baris Sheet: {item['sheet_row']}  |  ID: {item['id']}")

st.markdown(f"### Aspek: `{item['aspek']}`")

with st.container(border=True):
    st.markdown("**Teks Komentar**")
    teks_komentar = html.escape(item['teks']) if item['teks'] else '<i>(kosong)</i>'
    st.markdown(f"<div style='font-size:1.1rem'>{teks_komentar}</div>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("**Konteks**")
    konteks_teks = html.escape(item['konteks']) if item['konteks'] else '<i>(kosong)</i>'
    st.markdown(f"<div style='opacity:.85'>{konteks_teks}</div>", unsafe_allow_html=True)

st.info(f"**Prediksi Model:** `{item['prediksi'] if item['prediksi'] else '(kosong)'}`")

st.divider()

is_spam = st.checkbox(
    "Tandai sebagai SPAM (iklan / jualan produk / nomor WhatsApp)",
    value=(item["seharusnya"].upper() == "SPAM"),
    key=f"spam_{pos}"
)

val_benar = ""
val_seharusnya = ""
ready = False

if is_spam:
    val_benar = ""
    val_seharusnya = "SPAM"
    ready = True
    st.warning("Mode SPAM aktif: Kolom `benar` akan dikosongkan, `label_seharusnya` diisi `SPAM`, dan dikeluarkan dari hitungan.")
else:
    idx_benar = OPSI_BENAR.index(item["benar"]) if item["benar"] in OPSI_BENAR else None
    pilihan_benar = st.radio(
        "Apakah prediksi model sudah benar?",
        OPSI_BENAR,
        index=idx_benar,
        horizontal=True,
        key=f"benar_{pos}"
    )

    if pilihan_benar == "Ya":
        val_benar = "Ya"
        val_seharusnya = ""
        ready = True
    elif pilihan_benar == "Tidak":
        val_benar = "Tidak"
        opsi_koreksi = [o for o in OPSI_LABEL if o != item["prediksi"]] or OPSI_LABEL
        idx_seharusnya = opsi_koreksi.index(item["seharusnya"]) if item["seharusnya"] in opsi_koreksi else None
        pilihan_seharusnya = st.radio(
            "Pilih Label Seharusnya:",
            opsi_koreksi,
            index=idx_seharusnya,
            horizontal=True,
            key=f"seharusnya_{pos}"
        )
        if pilihan_seharusnya:
            val_seharusnya = pilihan_seharusnya
            ready = True

c1, c2 = st.columns(2)
with c1:
    if st.button("⬅ Back", disabled=pos == 0, use_container_width=True):
        st.session_state.pos -= 1
        st.rerun()
with c2:
    if st.button("Simpan & Next ➜", type="primary", disabled=not ready, use_container_width=True):
        with st.spinner("Menyimpan ke sheet..."):
            save_row(item, val_benar, val_seharusnya)
        st.session_state.pos += 1
        st.rerun()