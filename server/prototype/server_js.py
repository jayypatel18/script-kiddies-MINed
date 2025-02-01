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
    # Remove any remaining markdown or HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\*\*', '', text)
    # Normalize whitespace
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def generate_summary_iterative(text):
    chunk_size = 1200  # Reduced chunk size for better context handling
    chunks = chunk_text(text, chunk_size)
    
    combined_summary = ""
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i + 1}/{len(chunks)}...")
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral:7b-instruct',
                'prompt': f"""**Podcast Script Generation Task**
You are creating an engaging podcast script based on a research paper. Follow these rules STRICTLY:

1. TONE: Conversational and enthusiastic, like explaining to a curious friend. Use:
   - Rhetorical questions ("Now, you might be wondering...")
   - Conversational fillers ("Hmm, this is interesting...", "Okay, so...")
   - Self-interruptions ("Wait, let me clarify that...")
   - Natural pauses marked with (pause)

2. STRUCTURE:
   - Start with an intriguing hook related to the research
   - Introduce paper title and authors naturally
   - Explain key concepts through Q&A format
   - Use relatable analogies
   - Highlight surprising findings dramatically
   - End with thought-provoking conclusion

3. FORMATTING:
   - NO markdown, HTML, or special formatting
   - Use plain text only
   - Single newlines between paragraphs
   - No bullet points or numbered lists
   - Maximum 3 sentences per paragraph

4. CONTENT RULES:
   - Stay strictly faithful to paper content
   - No invented information
   - Simplify technical jargon
   - Acknowledge limitations where mentioned

Example format:
"Welcome back, listeners! Today we're diving into some fascinating research about... (pause) 
So what exactly did the team investigate? Well... (paper content explanation)
Wait, those results seem surprising! How did they...? (methodology explanation)
Hmm, but here's the kicker... (key findings)"

Not following these rules will result in a poor-quality script. And it is important to maintain the integrity of the research content.
Also do not hallucinate or invent any information. You are given a mission to create a podcast script based on the research paper.
Please follow the rules strictly. Not following the rules will result in a poor-quality script and will not be accepted.
Also it is not allowed to have enter \ n or anything like that or any other escape characters as this will directly affect the quality of the script and we are directly going to use text to speech and use it for the podcast so please make sure that you follow the rules strictly.
hence use of \ n or any other escape characters is not allowed and will deteriorate the quality of the script.

Now process this research content:
{chunk}""",
                'stream': False,
                'options': {
                    'temperature': 0.8,
                    'max_tokens': 20000,
                    'top_p': 0.85,
                    'repeat_penalty': 1.2
                }
            }
        )
        
        if response.status_code == 200:
            cleaned = clean_response(response.json()['response'])
            combined_summary += cleaned + "\n\n"
        else:
            combined_summary += f"(Technical difficulty with this segment - we'll skip ahead)\n\n"

    return combined_summary

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
    app.run(host='0.0.0.0', port=8000, debug=True)