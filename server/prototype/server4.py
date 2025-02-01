import os
import time
import requests
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import easyocr
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize EasyOCR reader for English (add more languages as needed)
ocr_reader = easyocr.Reader(['en'], gpu=False)

def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_page(page, pdf_path, page_index):
    """
    Attempt to extract text from a given PDF page with PyPDF2.
    If no text is found, render the page as an image and use EasyOCR.
    """
    try:
        page_text = page.extract_text()
        if page_text and page_text.strip():
            return page_text
        # If extract_text() returns None or empty, we rely on OCR.
        images = convert_from_path(
            pdf_path,
            first_page=page_index + 1,
            last_page=page_index + 1
        )
        # Use EasyOCR on all images (usually there's just one per page)
        ocr_text_parts = []
        for img in images:
            ocr_result = ocr_reader.readtext(img, detail=0)
            # detail=0 returns just the extracted text (list of strings).
            if ocr_result:
                # Join any recognized text into a single chunk
                ocr_text_parts.append(" ".join(ocr_result))
        return "\n".join(ocr_text_parts)
    except Exception as e:
        print(f"Error processing page {page_index + 1}: {e}")
        # Return empty string if OCR or extraction fails
        return ""

def extract_text_from_pdf(pdf_path):
    """
    Read an entire PDF file. For each page, first attempt text extraction
    via PyPDF2. If that fails or returns nothing, use EasyOCR to get page text.
    """
    overall_text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file, strict=False)  # strict=False for partial corruption tolerance
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for idx, page in enumerate(reader.pages):
                    futures.append(executor.submit(process_page, page, pdf_path, idx))
                for future in futures:
                    overall_text += future.result() + "\n"
    except Exception as e:
        print(f"Error reading PDF ({pdf_path}): {e}")
    return overall_text

def chunk_text(text, chunk_size=6000, overlap=1000):
    """
    Simple text chunking without a tokenizer.
    
    chunk_size: approximate character length for each chunk
    overlap: character overlap between chunks
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        
        # Find the nearest sentence end for a cleaner break
        if end < len(text):
            last_period = chunk.rfind('. ')
            if last_period != -1 and last_period > overlap:
                end = start + last_period + 1
                chunk = text[start:end]
        
        chunks.append(chunk)
        # Move start to end minus overlap for some continuity
        start = end - overlap if end - overlap > start else end
    return chunks

def generate_podcast(text):
    """
    Send text chunks to a local LLM endpoint for partial responses,
    then request a final combined podcast script. Retries on failure.
    """
    MAX_ATTEMPTS = 3
    attempt = 0
    
    while attempt < MAX_ATTEMPTS:
        try:
            chunks = chunk_text(text)
            conversation = [{
                "role": "user",
                "content": """I will send research paper chunks. Acknowledge with 'ACK' after each.
                            Retain all technical details. Final output will be a podcast script."""
            }]
            
            # Send chunks for partial responses
            for idx, chunk in enumerate(chunks):
                conversation.append({
                    "role": "user",
                    "content": f"CHUNK {idx+1}:\n{chunk}"
                })
                
                response = requests.post(
                    'http://localhost:11434/api/chat',
                    json={
                        "model": "llama3:latest",
                        "messages": conversation[-3:],  # Keep last 3 messages for context
                        "options": {"temperature": 0.2}
                    },
                    timeout=30
                )
                
                if not response.ok:
                    raise Exception(f"Chunk {idx+1} error: {response.text}")
                
                resp_json = response.json()
                if 'message' not in resp_json or 'content' not in resp_json['message']:
                    raise Exception(f"Chunk {idx+1} response missing 'content' field.")
                
                conversation.append({
                    "role": "assistant",
                    "content": resp_json['message']['content']
                })
            
            # Final request for a combined script
            conversation.append({
                "role": "user",
                "content": """Generate comprehensive podcast script covering:
                            1. Technical depth from all chunks
                            2. Methodology comparisons
                            3. Research implications
                            4. Future directions
                            Format: Dialogue between experts
                            Length: As needed for full coverage
                            Style: Academic yet engaging"""
            })
            
            final_response = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    "model": "llama3:latest",
                    "messages": [conversation[0], conversation[-1]],  # System prompt and final request
                    "options": {
                        "temperature": 0.6,
                        "max_tokens": 8000,
                        "top_p": 0.85
                    }
                },
                timeout=60
            )
            
            if final_response.ok:
                final_json = final_response.json()
                if 'message' in final_json and 'content' in final_json['message']:
                    return final_json['message']['content']
                else:
                    raise Exception("Final response missing 'content' field.")
            
            raise Exception("Final generation failed.")
        
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {str(e)}")
            attempt += 1
            time.sleep(2 ** attempt)
    
    return "Failed to generate podcast after multiple attempts."

@app.route('/process_pdfs', methods=['POST'])
def handle_pdfs():
    """
    This endpoint handles uploaded PDF files, extracts text, and generates
    a podcast-style summary via the local LLM. Returns the final script.
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    pdf_paths = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            pdf_paths.append(file_path)
    
    if not pdf_paths:
        return jsonify({'error': 'No valid PDF files'}), 400
    
    try:
        # Combine text from all PDF files
        combined_text = "\n\n".join(extract_text_from_pdf(path) for path in pdf_paths)
        # Generate a final "podcast" style summary
        podcast_script = generate_podcast(combined_text)
        
        # Cleanup: remove uploaded files
        for path in pdf_paths:
            if os.path.exists(path):
                os.remove(path)
        
        return jsonify({
            'podcast_script': podcast_script,
            'processed_files': [os.path.basename(p) for p in pdf_paths]
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_local', methods=['GET'])
def test_local_pdfs():
    """
    An example endpoint that looks for PDFs in the server directory starting
    with 'ref' and processes them without Tesseract, using EasyOCR if needed.
    """
    pdf_files = [f for f in os.listdir() if f.lower().startswith('ref') and f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No ref*.pdf files found'}), 404
    
    try:
        combined_text = "\n\n".join(extract_text_from_pdf(f) for f in pdf_files)
        podcast_script = generate_podcast(combined_text)
        
        return jsonify({
            'podcast_script': podcast_script,
            'processed_files': pdf_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Debug mode is enabled here for demonstration. In production, set debug=False.
    app.run(host='0.0.0.0', port=5000, debug=True)