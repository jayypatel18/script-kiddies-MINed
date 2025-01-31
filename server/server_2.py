import os
import shutil
import pytesseract
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
from PIL import Image
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 52428800000  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        # Extract text from PDF pages
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text.strip():
                    text += page_text + "\n"
                else:
                    # Convert page to image and OCR
                    images = convert_from_path(pdf_path, 
                                             first_page=page.page_number+1,
                                             last_page=page.page_number+1)
                    for image in images:
                        text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
    return text

def process_pdfs(pdf_paths):
    combined_text = ""
    for path in pdf_paths:
        print(f"Processing {path}...")
        combined_text += extract_text_from_pdf(path) + "\n\n"
    return combined_text.strip()

def generate_summary(text):
    try:
        print("Generating summary...")
        print(text)
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2:latest',
                'prompt': f"""Generate a comprehensive and indepth podcast script based on these research papers. 
                            
                            1. Introduction with context
                            2. Key findings and methodologies
                            3. Implications and future directions
                            4. Conclusion

                            Format as a natural dialogue between two researchers.
                            The content you generate should be solely from the research papers provided. please do not add any additional information nor change the context of the research papers nor hallucinate any information.
                            Follow the orders and the structure of the research
                            Papers content:\n\n{text}""",
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'max_tokens': 400000,
                    'top_p': 0.8
                }
            }
        )
        if response.status_code == 200:
            return response.json()['response']
        return f"Error: {response.text}"
    except Exception as e:
        return f"API Error: {str(e)}"

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
        combined_text = process_pdfs(pdf_paths)
        summary = generate_summary(combined_text)
        
        # Cleanup
        for path in pdf_paths:
            os.remove(path)
        
        return jsonify({
            'summary': summary,
            'combined_text': combined_text[:1000] + "..."  # Return first 1000 chars for debugging
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_local', methods=['GET'])
def test_local_pdfs():
    pdf_files = [f for f in os.listdir() if f.startswith('ref') and f.endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No ref*.pdf files found in directory'}), 404
    
    pdf_paths = [os.path.abspath(f) for f in pdf_files]
    try:
        combined_text = process_pdfs(pdf_paths)
        summary = generate_summary(combined_text)
        return jsonify({
            'summary': summary,
            'processed_files': pdf_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)