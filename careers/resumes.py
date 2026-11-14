"""Read an uploaded resume (PDF / DOCX / TXT) into plain text. Only the text is kept (in the private data store),
not the file. Limits stop huge or booby-trapped files: size, page count, text length, and a time cap."""
import base64
import io
import re
import time
import zipfile

MAX_FILE = 3 * 1024 * 1024        # 3 MB
MAX_PAGES = 6
MAX_TEXT = 20000
MAX_SECONDS = 8
MAX_RESUMES = 8
NAME_RE = re.compile(r"^[\w .()\-+&]{1,40}$")


class Bad(ValueError):
    pass


def _pdf(b):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(b))
    if r.is_encrypted:
        raise Bad("this PDF is password-protected — export it again without a password")
    if len(r.pages) > MAX_PAGES:
        raise Bad(f"more than {MAX_PAGES} pages — is this really a resume?")
    t0, out = time.time(), []
    for p in r.pages:
        out.append(p.extract_text() or "")
        if time.time() - t0 > MAX_SECONDS or sum(map(len, out)) > MAX_TEXT:
            break
    return "\n".join(out)


def _docx(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > 5 * 1024 * 1024:            # zip bomb guard
            raise Bad("document is too large inside")
        xml = z.read(info).decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", " ", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    import html
    return html.unescape(text)


def read(filename, data_b64):
    fn = str(filename or "").lower()
    try:
        b = base64.b64decode(str(data_b64 or ""), validate=True)
    except Exception:
        raise Bad("file didn't upload correctly")
    if not b or len(b) > MAX_FILE:
        raise Bad("file must be under 3 MB")
    try:
        if fn.endswith(".pdf") and b[:5] == b"%PDF-":
            text = _pdf(b)
        elif fn.endswith(".docx") and b[:2] == b"PK":
            text = _docx(b)
        elif fn.endswith((".txt", ".md")):
            text = b.decode("utf-8", "replace")
        else:
            raise Bad("upload a PDF, DOCX or TXT file")
    except Bad:
        raise
    except Exception as e:
        raise Bad(f"couldn't read the file ({type(e).__name__})")
    text = re.sub(r"[ \t]+", " ", text).strip()[:MAX_TEXT]
    if len(text) < 200:
        raise Bad("almost no text found — if it's a scanned image, export the resume as a text PDF")
    return text


def clean_name(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not NAME_RE.match(name):
        raise Bad("name: 1–40 letters, numbers, spaces or - . ( ) + &")
    return name
