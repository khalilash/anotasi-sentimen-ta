"""
Validasi ulang label akurasi yang ditandai merah di sheet.
Menampilkan penilaian dua dokter, lalu label final disimpan ke kolom T dan U.
"""
import html
import json

import gspread
import streamlit as st

SHEET_ID = "1O2KPLBGoChOUeRzpyu0wLVYhHiEyKZuPh_eA9lID1Go"
WS_NAME = "Sheet Gabungan"

# nomor baris di luar yang merah, kalau mau ikut ditampilkan. contoh: [42, 163, 164, 204, 210]
BARIS_TAMBAHAN = [210]

DOKTER_1 = "dr. Meidyta"
DOKTER_2 = "dr. Dyah"

# posisi kolom, A = 0
C_ID, C_POST, C_KOMENTAR = 0, 1, 2
C_DOK1, C_DOK2 = 4, 14          # E-H dan O-R
C_FINAL, C_ALASAN = 19, 20      # T dan U

URUTAN_KOLOM = ["Inaccurate", "Partially Accurate", "Accurate"]  # kolom_0, kolom_1, kolom_2

PILIHAN = {
    "Accurate": "Saran atau pernyataan medisnya sudah sesuai penanganan scabies yang tepat",
    "Partially Accurate": "Sebagian sudah tepat, sebagian kurang tepat atau berpotensi menyesatkan",
    "Inaccurate": "Tidak sesuai atau berpotensi membahayakan",
    # hapus baris di bawah kalau kategori ini belum disetujui
    "Tidak Berlaku": "Tidak memuat saran atau klaim penanganan scabies",
}
WAJIB_ALASAN = ["Partially Accurate", "Inaccurate"]

WARNA = {"Accurate": "#15803D", "Partially Accurate": "#B45309", "Inaccurate": "#B91C1C"}

st.set_page_config(page_title="Validasi Scabies", page_icon="🩺", layout="centered")

st.markdown(
    """
    <style>
    .block-container {max-width: 820px; padding-top: 3.5rem;}
    .judul {font-size: 1.6rem; font-weight: 700; line-height: 1.3;}
    .sub {opacity: .65;}
    .kecil {font-size: .72rem; font-weight: 700; letter-spacing: .07em; opacity: .55; margin-bottom: .35rem;}
    .post {line-height: 1.6; opacity: .85; white-space: pre-wrap; max-height: 11rem; overflow-y: auto; margin-bottom: .9rem;}
    .komentar {font-size: 1.22rem; line-height: 1.65; white-space: pre-wrap; padding-bottom: .6rem;}
    .st-key-komentar {border-left: 5px solid #0F766E;}
    .dua {display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .8rem; margin: .2rem 0 .6rem;}
    .dok {background: #fff; border: 1px solid #E2E8F0; border-top: 4px solid var(--w); border-radius: .7rem; padding: .9rem 1rem;}
    .badge {display: inline-block; background: var(--w); color: #fff; border-radius: 99px;
            padding: .15rem .75rem; font-size: .85rem; font-weight: 600;}
    .alasan {margin-top: .6rem; line-height: 1.55; font-size: .95rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_ws():
    info = json.loads(st.secrets["gspread_json"])
    gc = gspread.service_account_from_dict(info)
    return gc.open_by_key(SHEET_ID).worksheet(WS_NAME)


def baris_merah(ws):
    # baca warna latar kolom A
    meta = ws.client.fetch_sheet_metadata(
        ws.spreadsheet_id,
        params={
            "includeGridData": "true",
            "ranges": f"'{WS_NAME}'!A:A",
            "fields": "sheets(data(rowData(values(effectiveFormat(backgroundColor)))))",
        },
    )
    hasil = set()
    for no, baris in enumerate(meta["sheets"][0]["data"][0].get("rowData", []), start=1):
        sel = (baris.get("values") or [{}])[0]
        warna = sel.get("effectiveFormat", {}).get("backgroundColor", {})
        r, g, b = (warna.get(k, 0) for k in ("red", "green", "blue"))
        # merah tua maupun merah muda
        if r > 0.8 and g < 0.85 and b < 0.85 and abs(g - b) < 0.08:
            hasil.add(no)
    return hasil


def baca_dokter(baris, awal):
    dipilih = [URUTAN_KOLOM[i] for i in range(3) if baris[awal + i].strip()]
    label = dipilih[0] if len(dipilih) == 1 else None
    return label, baris[awal + 3].strip()


def muat_data():
    ws = get_ws()
    merah = baris_merah(ws) | set(BARIS_TAMBAHAN)
    data = []
    pilihan = {p.lower(): p for p in PILIHAN}
    for no, r in enumerate(ws.get_all_values(), start=1):
        r = r + [""] * (C_ALASAN + 1 - len(r))
        if no == 1 or no not in merah or not r[C_KOMENTAR].strip():
            continue
        data.append({
            "baris": no,
            "id": r[C_ID],
            "post": r[C_POST],
            "komentar": r[C_KOMENTAR],
            "dok1": baca_dokter(r, C_DOK1),
            "dok2": baca_dokter(r, C_DOK2),
            "final": pilihan.get(r[C_FINAL].strip().lower()),
            "alasan": r[C_ALASAN],
        })
    return data


def belum_diisi(data, mulai=0):
    urutan = list(range(mulai, len(data))) + list(range(0, mulai))
    return next((i for i in urutan if data[i]["final"] is None), None)


def simpan(item, label, alasan):
    ws = get_ws()
    r = item["baris"]
    # jaga-jaga kalau sheet diurutkan atau ada baris disisipkan
    if (ws.cell(r, C_KOMENTAR + 1).value or "").strip() != item["komentar"].strip():
        st.error("Susunan sheet berubah. Klik 'Muat ulang data', lalu isi lagi.")
        st.stop()
    ws.batch_update(
        [
            {"range": "T1:U1", "values": [["Final", "Alasan Final"]]},
            {"range": f"T{r}:U{r}", "values": [[label, alasan]]},
        ],
        value_input_option="RAW",
    )
    item["final"] = label
    item["alasan"] = alasan


def kartu_dokter(nama, penilaian):
    label, alasan = penilaian
    warna = WARNA.get(label, "#64748B")
    isi = html.escape(alasan) if alasan else "<i>Tanpa alasan</i>"
    return (
        f"<div class='dok' style='--w:{warna}'><div class='kecil'>{nama.upper()}</div>"
        f"<span class='badge'>{label or 'Belum jelas'}</span><div class='alasan'>{isi}</div></div>"
    )


def pindah(pos):
    st.session_state.pos = pos


def buka(kunci):
    st.session_state.pos = st.session_state[kunci] - 1


def muat_ulang():
    st.session_state.clear()


if "data" not in st.session_state:
    with st.spinner("Memuat data..."):
        st.session_state.data = muat_data()
    awal = belum_diisi(st.session_state.data)
    st.session_state.pos = len(st.session_state.data) if awal is None else awal

data = st.session_state.data
total = len(data)

if total == 0:
    st.info("Tidak ada baris bertanda merah di sheet.")
    st.button("Muat ulang data", on_click=muat_ulang)
    st.stop()

if st.session_state.pop("tersimpan", False):
    st.toast("Tersimpan", icon="✅")

jumlah = sum(x["final"] is not None for x in data)
st.markdown(
    "<div class='judul'>Validasi Ulang Akurasi Penanganan Scabies</div>"
    "<div class='sub'>Komentar berikut mendapat penilaian berbeda. Mohon tentukan label akhirnya.</div>",
    unsafe_allow_html=True,
)
st.progress(jumlah / total, text=f"{jumlah} dari {total} selesai · {total - jumlah} tersisa")

with st.expander("Panduan dan navigasi"):
    for nama, arti in PILIHAN.items():
        st.markdown(f"**{nama}**: {arti}")
    st.divider()
    kunci = f"lompat_{st.session_state.pos}"
    st.number_input("Buka komentar nomor", 1, total, min(st.session_state.pos + 1, total), key=kunci)
    k1, k2 = st.columns(2)
    k1.button("Buka", on_click=buka, args=(kunci,), width="stretch")
    k2.button("Muat ulang data", on_click=muat_ulang, width="stretch")

pos = st.session_state.pos

if pos >= total:
    sisa = belum_diisi(data)
    if sisa is None:
        st.success("Semua komentar sudah divalidasi. Terima kasih, Dok.")
        st.button("Lihat lagi komentar terakhir", on_click=pindah, args=(total - 1,))
    else:
        st.info(f"Masih ada {total - jumlah} komentar yang belum diisi.")
        st.button("Lanjutkan", type="primary", on_click=pindah, args=(sisa,))
    st.stop()

item = data[pos]
status = "SUDAH DIISI" if item["final"] else "BELUM DIISI"
st.caption(f"Komentar {pos + 1} dari {total} · {item['id']} · baris {item['baris']} · {status}")

with st.container(border=True):
    st.markdown(
        f"<div class='kecil'>POSTINGAN</div><div class='post'>{html.escape(item['post'])}</div>",
        unsafe_allow_html=True,
    )

with st.container(border=True, key="komentar"):
    st.markdown(
        f"<div class='kecil'>KOMENTAR YANG DINILAI</div><div class='komentar'>{html.escape(item['komentar'])}</div>",
        unsafe_allow_html=True,
    )

if item["dok1"][0] or item["dok2"][0]:
    st.markdown(
        f"<div class='dua'>{kartu_dokter(DOKTER_1, item['dok1'])}{kartu_dokter(DOKTER_2, item['dok2'])}</div>",
        unsafe_allow_html=True,
    )
else:
    st.info("Komentar ini belum punya label sebelumnya.")

opsi = list(PILIHAN)
label = st.radio(
    "**Label akhir**",
    opsi,
    index=opsi.index(item["final"]) if item["final"] else None,
    captions=list(PILIHAN.values()),
    key=f"label_{item['baris']}",
)
alasan = st.text_area(
    "Alasan (wajib untuk Partially Accurate dan Inaccurate)",
    value=item["alasan"],
    placeholder="Tuliskan alasan singkat",
    key=f"alasan_{item['baris']}",
)

kiri, kanan = st.columns([1, 2])
kiri.button("← Sebelumnya", disabled=pos == 0, on_click=pindah, args=(pos - 1,), width="stretch")
if kanan.button("Simpan & lanjut →", type="primary", width="stretch"):
    if label is None:
        st.warning("Pilih label akhirnya dulu.")
    elif label in WAJIB_ALASAN and not alasan.strip():
        st.warning(f"Untuk {label}, mohon isi alasannya.")
    else:
        try:
            with st.spinner("Menyimpan..."):
                simpan(item, label, alasan.strip())
        except gspread.exceptions.APIError:
            st.error("Gagal menyimpan. Tunggu sebentar lalu klik simpan lagi.")
            st.stop()
        st.session_state.tersimpan = True
        st.session_state.pos = pos + 1
        st.rerun()