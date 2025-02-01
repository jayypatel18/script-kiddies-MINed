import os
import time
import pytesseract
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
from PIL import Image
import requests
from concurrent.futures import ThreadPoolExecutor
from transformers import AutoTokenizer
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# OCR Configuration
POPPLER_PATH = os.getenv('POPPLER_PATH', 'C:/Users/Lenovo/Downloads/Release-24.08.0-0/poppler-24.08.0/Library/bin')
TESSDATA_PREFIX = os.getenv('TESSDATA_PREFIX', 'C:/Program Files/Tesseract-OCR/tessdata')

# Initialize tokenizer
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_page(page, pdf_path):
    try:
        page_text = page.extract_text()
        if page_text.strip():
            return page_text
        
        # OCR processing
        images = convert_from_path(
            pdf_path,
            first_page=page.page_number+1,
            last_page=page.page_number+1,
            poppler_path=POPPLER_PATH
        )
        return "\n".join([pytesseract.image_to_string(img, timeout=30) for img in images])
    
    except Exception as e:
        print(f"Error processing page: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for page in reader.pages:
                    futures.append(executor.submit(process_page, page, pdf_path))
                
                for future in futures:
                    text += future.result() + "\n"
    
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
    return text

def chunk_text(text, chunk_size=3000, overlap=500):
    tokens = tokenizer.encode(text)
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(tokens[start:end])
        start = end - overlap if (end - overlap) > start else end
        
    return [tokenizer.decode(chunk) for chunk in chunks]

def generate_podcast(text):
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
            
            for idx, chunk in enumerate(chunks):
                conversation.append({
                    "role": "user",
                    "content": f"CHUNK {idx+1}:\n{chunk}"
                })
                
                response = requests.post(
                    'http://localhost:11434/api/chat',
                    json={
                        "model": "llama3:latest",
                        "messages": conversation,
                        "options": {"temperature": 0.2}
                    },
                    timeout=30
                )
                
                if not response.ok:
                    raise Exception(f"Chunk {idx+1} error: {response.text}")
                
                conversation.append({
                    "role": "assistant",
                    "content": response.json()['message']['content']
                })
            
            # Final generation prompt
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
                    "messages": conversation,
                    "options": {
                        "temperature": 0.6,
                        "max_tokens": 8000,
                        "top_p": 0.85
                    }
                },
                timeout=60
            )
            
            if final_response.ok:
                return final_response.json()['message']['content']
            
            raise Exception("Final generation failed")
        
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {str(e)}")
            attempt += 1
            time.sleep(2 ** attempt)
    
    return "Failed to generate podcast after multiple attempts"

@app.route('/process_pdfs', methods=['POST'])
def handle_pdfs():
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
        combined_text = "\n\n".join(extract_text_from_pdf(path) for path in pdf_paths)
        podcast_script = generate_podcast(combined_text)
        
        # Cleanup
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
    app.run(host='0.0.0.0', port=5000, debug=True)