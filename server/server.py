import os
import pdfplumber
from flask import Flask, request, jsonify
from transformers import pipeline

app = Flask(__name__)

# ------------------------------------------------------------------------------
# 1) Initialize any necessary components, such as a summarization model
# ------------------------------------------------------------------------------
# Example: Using a BART-based summarization pipeline from Hugging Face
# Replace "facebook/bart-large-cnn" with your preferred model or local LLaMA setup
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a given PDF file using pdfplumber.
    """
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted_text.append(page.extract_text() or "")
    return "\n".join(extracted_text)

def chunk_text(text, max_chunk_length=1000):
    """
    Splits large text into smaller chunks to avoid exceeding model limits.
    Adjust 'max_chunk_length' according to the summarizer's max token size.
    """
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= max_chunk_length:
            chunks.append(" ".join(current_chunk))
            current_chunk = []

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def summarize_text(text):
    """
    Summarizes the input text using the Hugging Face pipeline in chunks
    (if necessary) to handle long documents.
    """
    chunks = chunk_text(text)
    summaries = []
    for chunk in chunks:
        # The 'min_length' and 'max_length' can be adjusted as desired
        result = summarizer(chunk, max_length=130, min_length=30, do_sample=False)
        summaries.append(result[0]['summary_text'])

    # Combine the partial summaries into a final summary
    return " ".join(summaries)

@app.route('/summarize-pdfs', methods=['GET'])
def summarize_pdfs():
    """
    - For demonstration, we directly read the PDFs named 'ref1.pdf' and 'ref2.pdf'
      from the current working directory.
    - If you want to receive files via ReactJS, you would instead implement
      a POST endpoint that reads the uploaded files from request.files.
    """
    pdf_files = ["./ref1.pdf", "./ref2.pdf"]  # Update or dynamically determine PDF filenames

    if not all(os.path.exists(pdf) for pdf in pdf_files):
        return jsonify({"error": "One or more specified PDF files do not exist."}), 400

    combined_text = []
    for pdf_file in pdf_files:
        pdf_text = extract_text_from_pdf(pdf_file)
        combined_text.append(pdf_text)

    # Join all extracted text from the multiple PDFs
    all_text = "\n".join(combined_text)

    # Summarize the combined text
    summary = summarize_text(all_text)

    # Return the summary as JSON
    return jsonify({"summary": summary}), 200

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True)