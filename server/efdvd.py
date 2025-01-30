import os
import time
import requests
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
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

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Optional: Path to poppler binaries (especially on Windows)
# Example: POPPLER_PATH = r'C:/path/to/poppler/bin'
POPPLER_PATH = r'C:/Users/Lenovo/Downloads/Release-24.08.0-0/poppler-24.08.0/Library/bin'

def allowed_file(filename):
    """
    Verify that the uploaded file is a PDF based on its extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ocr_page_as_image(pdf_path, page_index):
    """
    Convert a single page from the PDF to an image (via pdf2image)
    and run Tesseract OCR on it. Returns a string of extracted text.
    """
    text = ""
    try:
        # Convert from page N to N only
        images = convert_from_path(
            pdf_path,
            first_page=page_index + 1,
            last_page=page_index + 1,
            poppler_path=POPPLER_PATH or None
        )
        for img in images:
            text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        print(f"Error during OCR for page {page_index + 1}: {e}")
    return text

def process_page(page, pdf_path, page_index):
    """
    Attempt to extract text via PyPDF2. If that fails or is empty,
    convert the page to an image and use Tesseract OCR.
    """
    extracted_text = ""
    try:
        # Primary: use PyPDF2 to extract text
        py_text = page.extract_text()
        if py_text and py_text.strip():
            extracted_text = py_text
        else:
            # Fallback: Tesseract OCR on page image
            extracted_text = ocr_page_as_image(pdf_path, page_index)
    except Exception as e:
        print(f"Error processing page {page_index + 1}: {e}")
    return extracted_text.strip()

def extract_text_from_pdf(pdf_path):
    """
    Read all pages from the PDF and extract text.
    Uses strict=False to allow partial corruption parsing in PyPDF2.
    Pages are processed in parallel to speed up the workflow.
    """
    combined_text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file, strict=False)
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for idx, page in enumerate(reader.pages):
                    futures.append(executor.submit(process_page, page, pdf_path, idx))
                for future in futures:
                    combined_text += future.result() + "\n"
    except Exception as e:
        print(f"Error reading PDF '{pdf_path}': {e}")
    return combined_text

def chunk_text(text, chunk_size=6000, overlap=1000):
    """
    Break large text into overlapping segments for easier LLM consumption.
    chunk_size: the max length of each chunk (approx chars)
    overlap: portion of text repeated between consecutive chunks for context
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        
        # Attempt a cleaner boundary by looking for a period
        if end < len(text):
            last_period = chunk.rfind('. ')
            if last_period != -1 and last_period > overlap:
                end = start + last_period + 1
                chunk = text[start:end]
        
        chunks.append(chunk)
        # Slide by chunk_size - overlap (but never backward)
        start = end - overlap if (end - overlap) > start else end
    return chunks

def generate_podcast(text):
    """
    Sends chunked text to a local LLM endpoint to generate a final script.
    Retries a few times if errors occur.
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
            
            # Send each chunk for partial processing
            for idx, chunk in enumerate(chunks):
                conversation.append({
                    "role": "user",
                    "content": f"CHUNK {idx + 1}:\n{chunk}"
                })
                
                response = requests.post(
                    'http://localhost:11434/api/chat',
                    json={
                        "model": "llama3:latest",
                        "messages": conversation[-3:],  # keep references short
                        "options": {"temperature": 0.2}
                    },
                    timeout=30
                )
                
                if not response.ok:
                    raise Exception(f"Chunk {idx + 1} error: {response.text}")
                
                resp_json = response.json()
                if 'message' not in resp_json or 'content' not in resp_json['message']:
                    raise Exception(f"Missing 'content' in chunk {idx + 1} response.")
                
                conversation.append({
                    "role": "assistant",
                    "content": resp_json['message']['content']
                })
            
            # Finally, request a single combined podcast script:
            conversation.append({
                "role": "user",
                "content": """Generate a comprehensive podcast script covering:
                            1. Technical depth from all chunks
                            2. Methodology comparisons
                            3. Research implications
                            4. Future directions
                            Format: Dialogue between experts
                            Length: As needed
                            Style: Academic yet engaging"""
            })
            
            final_response = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    "model": "llama3:latest",
                    "messages": [conversation[0], conversation[-1]],
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
            print(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            time.sleep(2 ** attempt)
    
    return "Failed to generate podcast after multiple attempts."

@app.route('/process_pdfs', methods=['POST'])
def handle_pdfs():
    """
    POST /process_pdfs
    Accept one or more PDF files (key='files'), extract text (with fallback OCR),
    chunk the text, and produce a final 'podcast script' from your local LLM.
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
        combined_text = ""
        for path in pdf_paths:
            combined_text += extract_text_from_pdf(path) + "\n"
        
        # Generate a final "podcast"
        podcast_script = generate_podcast(combined_text)
        
        # Cleanup: remove uploaded PDFs
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
    GET /test_local
    Looks for PDFs starting with 'ref' in the current directory.
    Extracts text with fallback OCR, chunks it, and sends it to the LLM.
    """
    pdf_files = [f for f in os.listdir() if f.lower().startswith('ref') and f.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No ref*.pdf files found'}), 404
    
    try:
        combined_text = ""
        for pdf_file in pdf_files:
            combined_text += extract_text_from_pdf(pdf_file) + "\n"
        
        podcast_script = generate_podcast(combined_text)
        return jsonify({
            'podcast_script': podcast_script,
            'processed_files': pdf_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Debug mode is enabled here for demonstration. Disable in production.
    app.run(host='0.0.0.0', port=5000, debug=True)