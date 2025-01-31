import os
import requests
import time
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1500  # Reduced chunk size for reliability
OVERLAP = 200      # Context overlap
OLLAMA_TIMEOUT = 90  # Seconds

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class ProgressLogger:
    def __init__(self):
        self.start_time = time.time()
    
    def log(self, message):
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:.1f}s] {message}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path, logger):
    """Extract text with progress tracking"""
    logger.log(f"Starting extraction from {os.path.basename(pdf_path)}")
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            total_pages = len(reader.pages)
            for i, page in enumerate(reader.pages):
                text += page.extract_text() or ""
                if (i+1) % 5 == 0 or (i+1) == total_pages:
                    logger.log(f"Extracted {i+1}/{total_pages} pages")
    except Exception as e:
        logger.log(f"Extraction failed: {str(e)}")
        raise
    return text

def chunk_text(text, logger):
    """Create chunks with progress tracking"""
    logger.log("Starting chunking process")
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + CHUNK_SIZE, text_length)
        chunks.append(text[start:end])
        start = max(end - OVERLAP, start + 1)
        if len(chunks) % 5 == 0:
            logger.log(f"Created {len(chunks)} chunks")
    
    logger.log(f"Total chunks created: {len(chunks)}")
    return chunks

def ollama_chat(messages, logger, max_retries=3):
    """Robust API communication with timeout handling"""
    for attempt in range(max_retries):
        try:
            logger.log(f"API Attempt {attempt+1} with {len(messages)} messages")
            response = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    "model": "llama3.2:latest",
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.5}
                },
                timeout=OLLAMA_TIMEOUT
            )
            
            if response.status_code == 200:
                logger.log("API call successful")
                return response.json()['message']['content']
            
            logger.log(f"API error: {response.status_code} - {response.text}")
            
        except requests.exceptions.Timeout:
            logger.log("API timeout occurred")
        except Exception as e:
            logger.log(f"API connection error: {str(e)}")
        
        if attempt < max_retries-1:
            time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.log("API request failed after retries")
    return None

def generate_podcast(text, logger):
    """Full generation pipeline with logging"""
    logger.log("Starting podcast generation")
    chunks = chunk_text(text, logger)
    
    system_prompt = {
        "role": "user",
        "content": "You are a research assistant. Store information from these sections and acknowledge with 'ACK':"
    }
    context = [system_prompt]
    
    # Process chunks
    for idx, chunk in enumerate(chunks):
        logger.log(f"\nProcessing chunk {idx+1}/{len(chunks)}")
        messages = context[-2:] + [{
            "role": "user",
            "content": f"RESEARCH SECTION {idx+1}:\n{chunk}"
        }]
        
        response = ollama_chat(messages, logger)
        if not response:
            return "Error processing content"
        
        context.append(messages[-1])
        context.append({"role": "assistant", "content": response})
    
    # Final generation
    logger.log("\nStarting final synthesis")
    final_messages = [context[0], {
        "role": "user",
        "content": """Generate podcast script as dialogue covering:
        1. Introduction/context
        2. Key findings/methodologies
        3. Implications/future directions
        4. Conclusion
        Use ONLY provided research."""
    }]
    
    result = ollama_chat(final_messages, logger)
    logger.log("Generation complete" if result else "Final generation failed")
    return result or "Generation failed"

@app.route('/process_pdfs', methods=['POST'])
def handle_pdfs():
    logger = ProgressLogger()
    logger.log("New PDF processing request")
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    pdf_paths = []
    
    try:
        # Save uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                pdf_paths.append(file_path)
                logger.log(f"Saved: {filename}")
        
        if not pdf_paths:
            return jsonify({'error': 'No valid PDFs'}), 400
        
        # Process PDFs
        combined_text = ""
        for path in pdf_paths:
            combined_text += extract_text_from_pdf(path, logger) + "\n\n"
        
        podcast_script = generate_podcast(combined_text.strip(), logger)
        
        return jsonify({
            'podcast_script': podcast_script,
            'processed_files': [os.path.basename(p) for p in pdf_paths]
        })
        
    except Exception as e:
        logger.log(f"Critical error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup files
        for path in pdf_paths:
            try:
                os.remove(path)
                logger.log(f"Cleaned up: {path}")
            except:
                pass

@app.route('/test_local', methods=['GET'])
def test_local_pdfs():
    logger = ProgressLogger()
    logger.log("Test endpoint triggered")
    
    test_files = ['ref1.pdf', 'ref2.pdf']
    valid_files = []
    
    try:
        # Validate files
        for f in test_files:
            if os.path.exists(f):
                valid_files.append(f)
                logger.log(f"Found test file: {f}")
            else:
                logger.log(f"Missing test file: {f}")
        
        if not valid_files:
            return jsonify({'error': 'No test files found'}), 404
        
        # Process files
        combined_text = ""
        for f in valid_files:
            combined_text += extract_text_from_pdf(f, logger) + "\n\n"
        
        podcast_script = generate_podcast(combined_text.strip(), logger)
        
        return jsonify({
            'podcast_script': podcast_script,
            'processed_files': valid_files
        })
        
    except Exception as e:
        logger.log(f"Test error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting application...")
    app.run(host='0.0.0.0', port=8000, debug=True)