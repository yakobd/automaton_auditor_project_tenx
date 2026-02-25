from pathlib import Path
from docling.document_converter import DocumentConverter
from src.state import Evidence

def analyze_repo_pdf(repo_path: str) -> Evidence:
    repo_root = Path(repo_path)
    pdf_files = list(repo_root.rglob("*.pdf"))
    
    if not pdf_files:
        return Evidence(
            title="Documentation Coverage",
            severity=5,
            summary="No PDF files found in repository.",
            source="Docling",
        )

    pdf_path = pdf_files[0]

    try:
        converter = DocumentConverter()
        conversion_result = converter.convert(str(pdf_path))

        # Check if export_to_markdown is available, otherwise stringify
        if hasattr(conversion_result, "document") and hasattr(
            conversion_result.document, "export_to_markdown"
        ):
            text_content = conversion_result.document.export_to_markdown()
        else:
            text_content = str(conversion_result)

        # --- START OF RAG-LITE CHUNKING LOGIC ---
        # Splitting text into 500-character chunks
        chunks = [text_content[i:i+500] for i in range(0, len(text_content), 500)]
        
        keywords = ["graph", "state", "reducers"]
        found = set()

        # Querying the chunks (The RAG-lite approach)
        for chunk in chunks:
            normalized_chunk = chunk.lower()
            for kw in keywords:
                if kw in normalized_chunk:
                    found.add(kw)
        # --- END OF RAG-LITE CHUNKING LOGIC ---

        # Determine severity based on findings across chunks
        if len(found) == len(keywords):
            severity = 1
        elif found:
            severity = 3
        else:
            severity = 5

        return Evidence(
            title="Documentation Coverage",
            severity=severity,
            summary=f"Analyzed {pdf_path.name}; found keywords in chunks: {list(found)}",
            source="Docling",
        )
        
    except Exception as exc:
        return Evidence(
            title="Documentation Coverage",
            severity=5,
            summary=f"Failed to analyze PDF with Docling: {exc}",
            source="Docling",
        )