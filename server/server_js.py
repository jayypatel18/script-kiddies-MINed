import os
import pytesseract
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
from PIL import Image
import requests
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 52428800000  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Store summaries in memory for retrieval
results_storage = {}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text.strip():
                    text += page_text + "\n"
                else:
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

def chunk_text(text, chunk_size):
    """Splits text into smaller chunks."""
    chunks = []
    words = text.split()
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

def generate_summary_iterative(text):
    """Handles long texts by summarizing in chunks."""
    chunk_size = 1500  # Adjust this based on token limits
    chunks = chunk_text(text, chunk_size)
    
    combined_summary = ""
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i + 1}/{len(chunks)}...")
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3:latest',
                'prompt': f"""This is chunk {i + 1} of {len(chunks)}. 
                            Summarize the content of this research paper section for a podcast script:
                            
                            1. Introduction with context
                            2. Key findings and methodologies
                            3. Implications and future directions
                            4. Conclusion
                            
                            Do not add additional content. Text:\n\n{chunk}""",
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'max_tokens': 400000,
                    'top_p': 0.8
                }
            }
        )
        if response.status_code == 200:
            combined_summary += response.json()['response'] + "\n\n"
        else:
            combined_summary += f"Error in chunk {i + 1}: {response.text}\n\n"

    return combined_summary.strip()

# def generate_summary(text):
#     try:
#         print("Generating summary...")
#         response = requests.post(
#             'http://localhost:11434/api/generate',
#             json={
#                 'model': 'llama3:latest',
#                 'prompt': f"""Generate a comprehensive and in-depth podcast script based on these research papers. 
                            
#                             1. Introduction with context
#                             2. Key findings and methodologies
#                             3. Implications and future directions
#                             4. Conclusion

#                             Format as a natural dialogue between two researchers.
#                             The content you generate should be solely from the research papers provided. Please do not add any additional information nor change the context of the research papers nor hallucinate any information.
#                             Follow the order and the structure of the research.

#                             Papers content:\n\n{text}""",
#                 'stream': False,
#                 'options': {
#                     'temperature': 0.7,
#                     'max_tokens': 400000,
#                     'top_p': 0.8
#                 }
#             }
#         )
#         if response.status_code == 200:
#             return response.json()['response']
#         return f"Error: {response.text}"
#     except Exception as e:
#         return f"API Error: {str(e)}"

@app.route('/process_local', methods=['GET'])
def process_local_pdfs():
    pdf_files = [f for f in os.listdir() if f.startswith('ref') and f.endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No ref*.pdf files found in directory'}), 404

    pdf_paths = [os.path.abspath(f) for f in pdf_files]
    try:
        combined_text = process_pdfs(pdf_paths)
        
        # Use the iterative summarization function
        summary = generate_summary_iterative(combined_text)
        
        # Store the result in memory with a unique ID
        result_id = str(uuid.uuid4())
        results_storage[result_id] = {
            'summary': summary,
            'processed_files': pdf_files
        }
        
        return jsonify({
            'result_id': result_id,
            'summary': summary,
            'processed_files': pdf_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_summary/<result_id>', methods=['GET'])
def get_summary(result_id):
    # Fetch a stored summary based on the result ID
    if result_id in results_storage:
        return jsonify(results_storage[result_id])
    return jsonify({'error': 'Result not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)