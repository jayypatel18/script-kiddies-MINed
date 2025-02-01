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
        'concise': "Focus on key findings with minimal elaboration, using clear direct language",
        'elaborate': "Include detailed explanations with real-world examples and analogies",
        'balanced': "Balance key points with contextual information, using both facts and narrative",
        'formal': "Maintain academic tone with structured arguments and technical terminology",
        'casual': "Use conversational language with personal anecdotes and rhetorical questions",
        'professional': "Present well-researched insights with data references and expert quotes also use technical terms"
    }
    
    temperature, max_tokens = duration_map.get(duration, (0.78, 1500))
    
    combined_summary = ""
    title_added = False  # Track if title has been added
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}")
        
        # Structure instructions based on chunk position
        structure_rules = []
        if i == 0:
            structure_rules = [
                "BEGIN WITH: 'Title: \"[ENGAGING TITLE]\"' on first line",
                "Follow with host introduction that sets context",
                "Include brief overview of topics"
            ]
        elif i == len(chunks)-1:
            structure_rules = [
                "Conclude with key takeaways and final thoughts",
                "End with memorable closing statement",
                "Include call-to-action for listeners"
            ]
        else:
            structure_rules = [
                "Use natural transitions: 'Now, building on this...', 'Another crucial aspect...'",
                "Maintain narrative flow from previous content",
                "Include supporting examples or data points"
            ]

        prompt = f"""**Podcast Script Creation Guide**
Transform this research content into an engaging podcast script. Follow STRICTLY:

1. CONTENT STYLE: {style_instruction[content_style]}
2. TARGET DURATION: {duration.capitalize()} 
3. CORE STRUCTURE:
   - {structure_rules[0]}
   - {structure_rules[1]}
   - {structure_rules[2]}

**RULES:**
- FIRST CHUNK ONLY: Single title line at beginning
- NO MARKDOWN/HEADINGS in body text
- AVOID repetition between chunks
- USE conversational transitions between ideas
- BALANCE facts with engaging commentary
- INCLUDE 2-3 rhetorical questions per chunk
- CITE surprising statistics where available
- ADD relatable analogies for complex concepts
- NO EMOJIS or SPECIAL CHARACTERS
- ALSO ONLY THE PODCAST SCRIPT SHOULD BE GENERATED, NO NEED TO ASK FOR SUGGESTIONS AT THE END OF THE SCRIPT

**TONE:**
- Friendly yet authoritative
- Enthusiastic but professional
- Accessible to non-experts
- Vary sentence structure and length

**INPUT CONTENT:**
{chunk}

**PODCAST SCRIPT:**"""

        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3:latest',
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'top_p': 0.88,
                    'repeat_penalty': 1.25  # Increased to reduce repetition
                }
            }
        )
        
        if response.status_code == 200:
            cleaned = clean_response(response.json()['response'])
            
            # Post-processing rules
            if i > 0:
                # Remove any accidental titles in middle chunks
                cleaned = re.sub(r'Title: ".+?"\n', '', cleaned)
                # Remove section headers
                cleaned = re.sub(r'\b(Segment|Part) \d+:', '', cleaned, flags=re.IGNORECASE)
            
            # Ensure only one title exists
            if not title_added and re.search(r'Title: ".+?"', cleaned):
                title_added = True
            elif title_added:
                cleaned = re.sub(r'Title: ".+?"\n', '', cleaned)

            combined_summary += cleaned + " "

    # Final cleanup pipeline
    combined_summary = re.sub(r'\s+', ' ', combined_summary)
    combined_summary = re.sub(r'([,.!?:])(\w)', r'\1 \2', combined_summary)
    
    # Ensure single title format
    title_match = re.search(r'Title: ".+?"', combined_summary)
    if title_match:
        title = title_match.group(0)
        combined_summary = re.sub(r'Title: ".+?"\s*', '', combined_summary)
        combined_summary = f"{title}\n\n{combined_summary.strip()}"
    
    return combined_summary.strip()

@app.route('/generate', methods=['POST'])
def process_uploaded_pdfs():
    if 'pdfs' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('pdfs')
    content_style = request.form.get('contentStyle', 'concise')
    duration = request.form.get('duration', 'moderate')
    print(f"Content style: {content_style}, Duration: {duration}")
    # Check if files are uploaded
    print(files)

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
        print(f"Result ID: {result_id}")
        print(f"Summary: {summary}")
        print(f"Content style: {content_style}")
        print(f"Duration: {duration}")
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