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
import tempfile
from flask_cors import CORS 

load_dotenv()

app = Flask(__name__)
CORS(app)
# Configuration
UPLOAD_FOLDER = tempfile.mkdtemp()
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

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
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\*{2,}', '', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'\\n', ' ', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'([,.!?:])\s*', r'\1 ', text)
    text = re.sub(r'\(short pause\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\`\*\_\[\]\(\)\#\+\-]', '', text)
    return text.strip()

def generate_summary_iterative(text, content_style, duration):
    chunk_size = 1000
    chunks = chunk_text(text, chunk_size)
    
    duration_map = {
        'small': (0.85, 1200),
        'moderate': (0.78, 1500),
        'lengthy': (0.70, 2000)
    }
    
    style_instruction = {
        'concise': "Create a concise summary focusing on key findings",
        'elaborate': "Provide detailed explanations with examples"
    }
    
    temperature, max_tokens = duration_map.get(duration, (0.78, 1500))
    
    combined_summary = ""
    for i, chunk in enumerate(chunks):
        prompt = f"""**Podcast Script Creation**
Create an engaging podcast script from research content. Follow STRICTLY:

1. CONTENT STYLE: {style_instruction.get(content_style, '')}
2. TARGET DURATION: {duration.capitalize()}
3. TONE: Conversational, engaging, professional
4. STRUCTURE: Continuous flowing text without breaks

Input content:
{chunk}

Podcast script:"""

        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral:7b-instruct',
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature,
                    'max_tokens': max_tokens,
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

    combined_summary = re.sub(r'\s+', ' ', combined_summary)
    combined_summary = re.sub(r'([,.!?:])(\w)', r'\1 \2', combined_summary)
    return combined_summary.strip()

@app.route('/generate', methods=['POST'])
def process_uploaded_pdfs():
    if 'pdfs' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('pdfs')
    content_style = request.form.get('contentStyle', 'concise')
    duration = request.form.get('duration', 'moderate')
    
    if not files or len(files) == 0:
        return jsonify({'error': 'No files selected'}), 400
    
    saved_paths = []
    try:
        # Save uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                saved_paths.append(save_path)
        
        if not saved_paths:
            return jsonify({'error': 'No valid PDF files uploaded'}), 400
        
        # Process PDFs
        combined_text = process_pdfs(saved_paths)
        summary = generate_summary_iterative(combined_text, content_style, duration)
        
        # Create result entry
        result_id = str(uuid.uuid4())
        results_storage[result_id] = {
            'summary': summary,
            'content_style': content_style,
            'duration': duration,
            'processed_files': [os.path.basename(p) for p in saved_paths]
        }
        
        # Cleanup uploaded files
        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)
        
        return jsonify({
            'result_id': result_id,
            'summary': summary,
            'content_style': content_style,
            'duration': duration
        })
    
    except Exception as e:
        # Cleanup files on error
        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)
        return jsonify({'error': str(e)}), 500

@app.route('/get_summary/<result_id>', methods=['GET'])
def get_summary(result_id):
    if result_id in results_storage:
        return jsonify(results_storage[result_id])
    return jsonify({'error': 'Result not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)