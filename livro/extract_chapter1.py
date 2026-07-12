import pdfplumber

pdf_path = r"c:\Users\ev_ro\git\gemeos-digitais\livro\01 - Manisha Vohra - Digital Twin Technology_ Fundamentals and Applications (2022, Wiley-Scrivener) - libgen.li.pdf"

output_path = r"c:\Users\ev_ro\git\gemeos-digitais\livro\capitulo4_texto_extraido.txt"

with pdfplumber.open(pdf_path) as pdf:
    chapter4_text = []
    # Chapter 4 spans pages 67-96 (0-indexed: 66-95, range is 66 to 96)
    for i in range(66, 96):
        page = pdf.pages[i]
        text = page.extract_text()
        if text:
            chapter4_text.append(f"--- Página {i+1} ---\n")
            chapter4_text.append(text)
            chapter4_text.append("\n\n")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(chapter4_text))

print(f"Texto extraído do Capítulo 4 salvo em: {output_path}")
print(f"Total de caracteres: {sum(len(t) for t in chapter4_text)}")
