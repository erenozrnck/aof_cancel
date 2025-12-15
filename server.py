from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import Response, FileResponse
import fitz  # PyMuPDF
import re
import collections
import os
from statistics import median

app = FastAPI()

@app.get("/")
async def read_index():
    return FileResponse("index.html")

# --- Unicode ve "İ" için güvenli TTF fontlar ---
# Yanına DejaVuSans.ttf indirmen gerekebilir ya da sistem yolunu ekle.
FONT_CANDIDATES_REG = [
    "DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_CANDIDATES_BOLD = [
    "DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica-Bold.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

def pick_font(candidates: list[str]) -> str:
    for p in candidates:
        if os.path.exists(p):
            return p
    # Fallback: eğer hiçbiri yoksa varsayılan olarak "hels" (Helvetica) dönebiliriz 
    # ama o zaman Türkçe karakterde (İ) sorun çıkabilir.
    # Şimdilik yine hata fırlatalım veya hardcode bir yol deneyelim.
    print(f"Uyarı: Font bulunamadı, varsayılan fontlar denendi: {candidates}")
    return "helv"  # PyMuPDF built-in font fallback

FONT_REG = pick_font(FONT_CANDIDATES_REG)
FONT_BOLD = pick_font(FONT_CANDIDATES_BOLD)

# fontname boşluk içermemeli
FN_REG = "EmbedReg"
FN_BOLD = "EmbedBold"


def parse_cancelled(s: str) -> list[int]:
    parts = re.split(r"[\s,;]+", (s or "").strip())
    nums = []
    for p in parts:
        if not p:
            continue
        try:
            n = int(p)
            if n > 0:
                nums.append(n)
        except:
            pass
    return sorted(set(nums))


def get_fontsize_stats(page: fitz.Page):
    """
    Sayfadaki span font size'larını toplayıp 'soru metni' ve 'soru numarası' için
    yaklaşık bir puntolama çıkarır.
    """
    d = page.get_text("dict")
    body_sizes = []
    boldish_sizes = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                txt = (s.get("text") or "").strip()
                sz = float(s.get("size") or 0)
                font = (s.get("font") or "").lower()
                if not txt or sz <= 0:
                    continue

                # Metin gövdesi: "A)" "B)" seçenek satırları ve normal cümleler
                if re.match(r"^[A-E]\)", txt) or (len(txt) > 6 and not re.fullmatch(r"\d+\.", txt)):
                    body_sizes.append(sz)

                # Bold-ish (font adında bold/black geçiyorsa) — başlık veya soru no olabilir
                if "bold" in font or "black" in font:
                    boldish_sizes.append(sz)

    # Güvenli varsayılanlar
    body_fs = median(body_sizes) if body_sizes else 11.0
    bold_fs = median(boldish_sizes) if boldish_sizes else max(12.0, body_fs)

    return body_fs, bold_fs


def apply_cancellations(pdf_bytes: bytes, cancelled_questions: list[int]) -> bytes:
    cancelled = set(cancelled_questions)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # --- 1) Soruları iptal et: ilgili soru bloğunu beyazla + aynı puntoda metni bas ---
    for pno in range(doc.page_count):
        page = doc[pno]
        d = page.get_text("dict")

        # sayfadaki tipik puntoları ölç
        body_fs, bold_fs = get_fontsize_stats(page)

        qspans = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    t = (s.get("text") or "").strip()
                    if re.fullmatch(r"\d+\.", t):  # "12."
                        q = int(t[:-1])
                        x0, y0, x1, y1 = s["bbox"]
                        qspans.append((q, x0, y0, x1, y1))

        if not qspans:
            continue

        width = page.rect.width
        height = page.rect.height
        mid = width / 2

        cols = {"L": [], "R": []}
        for q, x0, y0, x1, y1 in qspans:
            col = "L" if x0 < mid else "R"
            cols[col].append((q, x0, y0, x1, y1))

        insert_ops = []   # (x, y, msg, fs)
        redaction_count = 0

        for col, items in cols.items():
            if not items:
                continue
            items = sorted(items, key=lambda t: t[2])  # y0

            # iki sütun şablonu
            margin = 50
            gutter = 20
            if col == "L":
                cx0 = margin
                cx1 = mid - gutter
            else:
                cx0 = mid + gutter
                cx1 = width - margin

            for idx, (q, x0, y0, x1, y1) in enumerate(items):
                if q not in cancelled:
                    continue

                y_top = y0 - 2
                if idx < len(items) - 1:
                    y_bottom = items[idx + 1][2] - 6
                else:
                    y_bottom = height - 60  # footer'ı ezmemek için

                # Metni soru numarasının hizasına bas:
                # Soru numarasını (x0..x1) korumak için, redaction x1'den başlasın
                redact_x0 = x1 + 2
                rect = fitz.Rect(redact_x0, y_top, cx1, y_bottom)

                # bloğu beyazla (redaction)
                page.add_redact_annot(rect, fill=(1, 1, 1))
                redaction_count += 1

                # Metni soru numarasının sağına bas
                msg = "Bu soru iptal edilmiştir"
                insert_ops.append((redact_x0 + 5, y0 + (body_fs * 0.9), msg, body_fs))

        if redaction_count:
            page.apply_redactions()
            for x, y, msg, fs in insert_ops:
                # normal sorular gibi siyah ama BOLD
                page.insert_text(
                    (x, y),
                    msg,
                    fontsize=fs,
                    fontname=FN_BOLD,
                    fontfile=FONT_BOLD,
                    color=(0, 0, 0),
                )

    # --- 2) Cevap anahtarı: harfi kapat + kırmızı "İ" bas ---
    ak_page_no = None
    for pno in range(doc.page_count):
        if doc[pno].search_for("Cevap Anahtarı"):
            ak_page_no = pno
            break

    if ak_page_no is not None and cancelled:
        page = doc[ak_page_no]
        d = page.get_text("dict")

        # cevap harf span'larını topla
        candidates = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    t = (s.get("text") or "").strip()
                    if len(t) == 1 and t in "ABCDE":
                        x0, y0, x1, y1 = s["bbox"]
                        candidates.append((x0, y0, x1, y1, float(s.get("size") or 11.0)))

        if candidates:
            # satırları y'ye göre grupla
            buckets = collections.defaultdict(list)
            for x0, y0, x1, y1, sz in candidates:
                buckets[round(y0, 1)].append((x0, y0, x1, y1, sz))

            # en kalabalık satır cevap satırı olsun
            best_y = max(buckets.keys(), key=lambda k: len(buckets[k]))
            row = sorted(buckets[best_y], key=lambda r: r[0])

            for q in cancelled:
                idx = q - 1
                if 0 <= idx < len(row):
                    x0, y0, x1, y1, sz = row[idx]

                    # mevcut harfi beyazla kapat
                    page.draw_rect(
                        fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1),
                        fill=(1, 1, 1),
                        color=None
                    )

                    # kırmızı İ (Unicode U+0130) — TTF ile garanti
                    # baseline için y1'e yakın yazdır
                    page.insert_text(
                        (x0, y1 - 0.7),
                        "İ",
                        fontsize=sz,
                        fontname=FN_REG,
                        fontfile=FONT_REG,
                        color=(1, 0, 0)
                    )

    out = doc.tobytes()
    doc.close()
    return out


@app.post("/cancel")
async def cancel(pdf: UploadFile, iptal: str = Form("")):
    cancelled = parse_cancelled(iptal)
    pdf_bytes = await pdf.read()
    out = apply_cancellations(pdf_bytes, cancelled)
    return Response(content=out, media_type="application/pdf")
