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
                'model': 'deepseek-r1:14b',
                'prompt': f"""This is chunk {i + 1} of {len(chunks)}. 
                            You are generating a podcast script based on a research paper. Your task is to summarize the paper in a structured and engaging manner. Follow this format strictly:

                            Start with the paper's title and mention the authors.
                            Provide an engaging introduction that briefly explains the research topic and its relevance.
                            Summarize the key sections of the paper, including:
                            The research objective and the problem it addresses.
                            The methodology used by the researchers.
                            The main findings and their significance.
                            Discuss the implications of the research, including its potential applications or impact.
                            Conclude with the key takeaway from the paper, highlighting the main contributions.
                            If the paper includes references, briefly mention that the authors cited prior works but do not generate specific details about them.
                            Important Rules:

                            Do not make up information or add content beyond what is present in the paper.
                            Do not include the references section of the paper in the summary.
                            Maintain a natural, engaging, and fluent tone as if narrating to an audience.
                            The output should be in plain English with normal punctuation (no markdown, no unnecessary formatting).
                            Also it is compulsory for you to follow the rules strictly. If you fail to do so, your response will be rejected. 
                            And the most important thing is that give output in plain text, no need for /n or html tags or markdown only plain text
                            
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