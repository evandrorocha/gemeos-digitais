import subprocess
import re
from pathlib import Path

def convert_md_to_pdf():
    docs_dir = Path(__file__).resolve().parent
    md_path = docs_dir / "ARQUITETURA.md"
    html_path = docs_dir / "ARQUITETURA.html"
    pdf_path = docs_dir / "ARQUITETURA.pdf"

    content = md_path.read_text(encoding="utf-8")

    # Tratamento de Imagens locais Markdown -> HTML
    def handle_image(match):
        alt = match.group(1)
        src = match.group(2)
        img_full_path = (docs_dir / src).resolve().as_uri()
        return f'<div class="figure-box"><img src="{img_full_path}" alt="{alt}"><br><span class="caption">{alt}</span></div>'

    html_body = re.sub(r"!\[(.*?)\]\((.*?)\)", handle_image, content)

    # Tratamento de blocos de código
    def handle_code_block(match):
        code = match.group(2).strip()
        safe_code = code.replace("<", "&lt;").replace(">", "&gt;")
        return f'<pre><code>{safe_code}</code></pre>'

    html_body = re.sub(r"```([a-zA-Z0-9_-]+)?\s*\n(.*?)```", handle_code_block, html_body, flags=re.DOTALL)

    # Conversão de cabeçalhos
    html_body = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", html_body, flags=re.MULTILINE)

    # Formatação de texto
    html_body = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html_body)
    html_body = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html_body)
    html_body = re.sub(r"`(.*?)`", r"<code>\1</code>", html_body)
    html_body = re.sub(r"^---$", r"<hr>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^\* (.*?)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^\d+\. (.*?)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)
    html_body = html_body.replace("\n\n", "<p></p>")

    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Arquitetura do Gêmeo Digital</title>
<style>
    @page {{
        size: A4;
        margin: 15mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.55;
        color: #1e293b;
        background-color: #ffffff;
        padding: 0;
    }}
    h1 {{
        color: #1e3a8a;
        font-size: 22pt;
        border-bottom: 2px solid #1e3a8a;
        padding-bottom: 6px;
        margin-top: 0;
        margin-bottom: 12px;
    }}
    h2 {{
        color: #0d9488;
        font-size: 15pt;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 4px;
        margin-top: 24px;
        margin-bottom: 10px;
    }}
    h3 {{
        color: #334155;
        font-size: 12pt;
        margin-top: 18px;
        margin-bottom: 8px;
    }}
    p, li {{
        font-size: 10pt;
        margin-bottom: 4px;
    }}
    code {{
        background-color: #f1f5f9;
        color: #0f172a;
        padding: 2px 4px;
        border-radius: 4px;
        font-family: 'Consolas', monospace;
        font-size: 9pt;
    }}
    pre {{
        background-color: #0f172a;
        color: #f8fafc;
        padding: 12px;
        border-radius: 6px;
        overflow-x: auto;
        font-family: 'Consolas', monospace;
        font-size: 8.5pt;
        line-height: 1.4;
        margin: 10px 0;
    }}
    pre code {{
        background-color: transparent;
        color: inherit;
        padding: 0;
    }}
    hr {{
        border: 0;
        height: 1px;
        background: #e2e8f0;
        margin: 16px 0;
    }}
    ul, ol {{
        padding-left: 20px;
        margin-top: 4px;
        margin-bottom: 8px;
    }}
    li {{
        margin-bottom: 3px;
    }}
    .figure-box {{
        text-align: center;
        margin: 16px 0;
        page-break-inside: avoid;
    }}
    .figure-box img {{
        max-width: 100%;
        height: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.06);
    }}
    .caption {{
        color: #64748b;
        font-style: italic;
        font-size: 8.5pt;
        display: block;
        margin-top: 6px;
    }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    html_path.write_text(full_html, encoding="utf-8")

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not Path(edge_bin).exists():
        edge_bin = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    cmd = [
        edge_bin,
        "--headless",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--enable-local-file-accesses",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        str(html_path.resolve())
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    print(f"Sucesso! PDF completo gerado em: {pdf_path}")
    print(f"Tamanho do PDF: {pdf_path.stat().st_size} bytes")

if __name__ == "__main__":
    convert_md_to_pdf()
