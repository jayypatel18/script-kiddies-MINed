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
import re

load_dotenv()

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 52428800000  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

results_storage = {}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        combined_text += extract_text_from_pdf(path) + "\n\n"
    return combined_text.strip()

def chunk_text(text, chunk_size):
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence.split())
        if current_length + sentence_length > chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(sentence)
        current_length += sentence_length
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def clean_response(text):
    # Remove markdown and special characters
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\*{2,}', '', text)
    text = re.sub(r'_{2,}', '', text)
    
    # Handle newlines and whitespace
    text = re.sub(r'\\n', ' ', text)  # Remove escaped newlines
    text = re.sub(r'\n', ' ', text)    # Replace ALL newlines with spaces
    text = re.sub(r'\s+', ' ', text)   # Collapse multiple whitespace
    text = re.sub(r'([,.!?:])\s*', r'\1 ', text)  # Normalize punctuation spacing
    
    # Remove pause indicators and special characters
    text = re.sub(r'\(short pause\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\`\*\_\[\]\(\)\#\+\-]', '', text)
    
    return text.strip()

def generate_summary_iterative(text):
    chunk_size = 1000
    chunks = chunk_text(text, chunk_size)
    
    combined_summary = ""
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i + 1}/{len(chunks)}...")
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral:7b-instruct',
                'prompt': f"""**Podcast Script Creation**
Create an engaging podcast script from research content. Follow STRICTLY:

1. TONE:
   - Conversational host explaining to curious listeners
   - Use natural speech patterns: "Hmm...", "Wait...", "So here's something interesting..."
   - Include 2-3 rhetorical questions per segment
   - NO pause indicators or timing notes

2. STRUCTURE:
   - Continuous flowing text without line breaks
   - Max 4 sentences per paragraph
   - No bullet points, lists, or markdown
   - No special formatting of any kind

3. CONTENT RULES:
   - Stay 100% faithful to source material
   - Simplify technical terms naturally
   - Highlight surprising findings
   - Mention limitations if present

4. STRICT FORMATTING:
   - Only use normal punctuation
   - No line breaks or paragraph separators
   - Never use special characters
   - Maintain continuous prose

BAD EXAMPLE (to avoid):
- "Welcome back! (short pause) Today we're..."
- Using any parentheses for timing
- Line breaks between sentences

GOOD EXAMPLE:
"Welcome back! Today we're exploring groundbreaking research about AI in healthcare. Now you might be wondering, how did they approach this complex problem? Let me walk you through their innovative solution. The team developed a novel framework combining..."

Input content:
{chunk}

Podcast script:""",
                'stream': False,
                'options': {
                    'temperature': 0.78,
                    'max_tokens': 1500,
                    'top_p': 0.88,
                    'repeat_penalty': 1.15
                }
            }
        )
        
        if response.status_code == 200:
            cleaned = clean_response(response.json()['response'])
            combined_summary += cleaned + " "
        else:
            combined_summary += "[Transition] "

    # Final cleanup pass
    combined_summary = re.sub(r'\s+', ' ', combined_summary)
    combined_summary = re.sub(r'([,.!?:])(\w)', r'\1 \2', combined_summary)
    return combined_summary.strip()

@app.route('/process_local', methods=['GET'])
def process_local_pdfs():
    pdf_files = [f for f in os.listdir() if f.startswith('ref') and f.endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No ref*.pdf files found'}), 404

    try:
        combined_text = process_pdfs([os.path.abspath(f) for f in pdf_files])
        summary = generate_summary_iterative(combined_text)
        
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
    if result_id in results_storage:
        return jsonify(results_storage[result_id])
    return jsonify({'error': 'Result not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)