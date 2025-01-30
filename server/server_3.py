import os
import re
import tempfile
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
MAX_TOKENS_PER_CHUNK = 3000  # Adjusted for Llama 3's context window

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_text(text):
    """Clean and normalize extracted text"""
    text = re.sub(r'\s+', ' ', text)  # Replace multiple whitespace
    text = re.sub(r'(.)\1{3,}', r'\1', text)  # Remove repeated characters
    return text.strip()

def extract_text_from_pdf(pdf_path):
    """Improved text extraction with hybrid approach"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                # First try text extraction
                page_text = page.extract_text()
                if page_text and len(page_text) > 50:  # Check for meaningful text
                    text += clean_text(page_text) + "\n"
                else:
                    # Fallback to OCR
                    with tempfile.TemporaryDirectory() as temp_dir:
                        images = convert_from_path(
                            pdf_path,
                            dpi=300,
                            first_page=i+1,
                            last_page=i+1,
                            output_folder=temp_dir,
                            fmt='jpeg'
                        )
                        for img in images:
                            ocr_text = pytesseract.image_to_string(img)
                            text += clean_text(ocr_text) + "\n"
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
    return text

def chunk_text(text, max_length=MAX_TOKENS_PER_CHUNK):
    """Split text into semantically meaningful chunks"""
    paragraphs = [p for p in text.split('\n') if p.strip()]
    chunks = []
    current_chunk = []
    
    for para in paragraphs:
        if sum(len(p) for p in current_chunk) + len(para) < max_length:
            current_chunk.append(para)
        else:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [para]
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks

def generate_summary_chunk(chunk):
    """Process a single text chunk with LLM"""
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3:latest',
                'prompt': f"""Analyze this research paper section and extract key points for a podcast script:
                            Focus on:
                            - Main arguments
                            - Novel methodologies
                            - Significant findings
                            - Critical conclusions
                            - Interesting data points
                            
                            Section Content:\n{chunk}""",
                'stream': False,
                'options': {
                    'temperature': 0.6,
                    'max_tokens': 2000,
                    'top_p': 0.8,
                    'repeat_penalty': 1.2
                }
            },
            timeout=60
        )
        return response.json()['response'] if response.status_code == 200 else ""
    except Exception as e:
        print(f"API Error: {str(e)}")
        return ""

def assemble_podscript(chunk_summaries):
    """Combine chunk summaries into final podcast script"""
    combined = "\n\n".join(chunk_summaries)
    
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3:latest',
                'prompt': f"""Create a natural-sounding podcast script from these research insights:
                            Structure:
                            1. Introduction with context
                            2. Key findings section
                            3. Methodology discussion
                            4. Implications analysis
                            5. Conclusion & future directions
                            
                            Format as dialogue between two researchers. Maintain academic rigor but keep it engaging.
                            
                            Research Insights:\n{combined}""",
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'max_tokens': 4000,
                    'top_p': 0.85
                }
            },
            timeout=120
        )
        return response.json()['response'] if response.status_code == 200 else "Error in final assembly"
    except Exception as e:
        return f"Assembly Error: {str(e)}"

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
        combined_text = "\n".join(extract_text_from_pdf(path) for path in pdf_paths)
        chunks = chunk_text(combined_text)
        
        # Process chunks in sequence
        chunk_summaries = [generate_summary_chunk(chunk) for chunk in chunks]
        final_script = assemble_podscript(chunk_summaries)
        
        # Cleanup
        for path in pdf_paths:
            os.remove(path)
        
        return jsonify({
            'podcast_script': final_script,
            'processed_chunks': len(chunks)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)