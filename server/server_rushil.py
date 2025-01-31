# # import os
# # import time
# # import logging
# # import requests
# # from flask import Flask, jsonify, request
# # from werkzeug.utils import secure_filename
# # from PyPDF2 import PdfReader

# # app = Flask(__name__)

# # # Configuration Constants
# # UPLOAD_FOLDER = 'uploads'
# # ALLOWED_EXTENSIONS = {'pdf'}
# # MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
# # CHUNK_SIZE = 2500  # Conservative chunk size
# # OVERLAP = 400      # Character overlap between chunks
# # API_MAX_TOKENS = 10000
# # API_TIMEOUT = 90

# # app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# # app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# # # Configure logging
# # logging.basicConfig(level=logging.INFO)
# # logger = logging.getLogger('PDFProcessor')

# # # Ensure upload directory exists
# # os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # def allowed_file(filename):
# #     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# # def robust_text_extraction(pdf_path):
# #     """Improved PDF text extraction with error handling"""
# #     text = ""
# #     try:
# #         with open(pdf_path, 'rb') as file:
# #             reader = PdfReader(file)
# #             for page in reader.pages:
# #                 try:
# #                     page_text = page.extract_text()
# #                     if page_text:
# #                         text += page_text + "\n"
# #                 except Exception as page_error:
# #                     logger.warning(f"Page extraction error: {page_error}")
# #         return text.strip()
# #     except Exception as e:
# #         logger.error(f"PDF extraction failed: {e}")
# #         return ""

# # def smart_chunking(text):
# #     """Text chunking with sentence boundary awareness"""
# #     chunks = []
# #     start = 0
# #     text_length = len(text)
    
# #     while start < text_length:
# #         end = min(start + CHUNK_SIZE, text_length)
        
# #         # Find sentence boundary
# #         boundary_chars = {'.', '!', '?', '\n\n', '\r\n\r\n'}
# #         while end > start + (CHUNK_SIZE // 2) and end < text_length:
# #             if text[end] in boundary_chars:
# #                 break
# #             end -= 1
        
# #         # Fallback to fixed chunking
# #         if end <= start:
# #             end = start + CHUNK_SIZE
        
# #         chunk = text[start:end].strip()
# #         if chunk:
# #             chunks.append(chunk)
        
# #         # Update start with overlap
# #         start = max(end - OVERLAP, start + 1)
    
# #     return chunks

# # def ollama_api_call(payload):
# #     """Robust API communication handler"""
# #     try:
# #         response = requests.post(
# #             'http://localhost:11434/api/chat',
# #             json=payload,
# #             timeout=API_TIMEOUT
# #         )
        
# #         if response.status_code == 200:
# #             return response.json().get('message', {}).get('content', '')
        
# #         logger.error(f"API Error {response.status_code}: {response.text}")
# #         return None
        
# #     except requests.exceptions.JSONDecodeError:
# #         logger.error("Invalid JSON response from API")
# #         return None
# #     except requests.exceptions.RequestException as e:
# #         logger.error(f"Request failed: {str(e)}")
# #         return None

# # def generate_podcast_script(text):
# #     """Main processing pipeline with context management"""
# #     chunks = smart_chunking(text)
# #     if not chunks:
# #         return "Error: No valid text chunks generated"
    
# #     context = [{
# #         "role": "system",
# #         "content": "You are a technical research assistant. Acknowledge content with 'CONTENT RECEIVED'."
# #     }]
    
# #     # Process chunks with context
# #     for idx, chunk in enumerate(chunks):
# #         user_message = {
# #             "role": "user",
# #             "content": f"RESEARCH DATA PART {idx+1}:\n{chunk}"
# #         }
        
# #         # Maintain rolling context window
# #         messages = context[-2:] + [user_message]
        
# #         payload = {
# #             "model": "llama3.2:latest",
# #             "messages": messages,
# #             "stream": False,
# #             "options": {
# #                 "temperature": 0.4,
# #                 "max_tokens": 3000
# #             }
# #         }
        
# #         response = ollama_api_call(payload)
# #         if response:
# #             context.extend([user_message, {"role": "assistant", "content": response}])
# #             logger.info(f"Processed chunk {idx+1}/{len(chunks)}")
# #         else:
# #             logger.warning(f"Failed chunk {idx+1}, continuing...")
    
# #     # Final generation
# #     final_payload = {
# #         "model": "llama3.2:latest",
# #         "messages": [context[0], {
# #             "role": "user",
# #             "content": """Generate podcast script with this structure:
# #                         1. Introduction (context, background)
# #                         2. Methodologies (research approaches)
# #                         3. Key Findings (discoveries)
# #                         4. Implications (significance)
# #                         5. Conclusion (summary)
# #                         Format: Natural dialogue between experts
# #                         Use only provided content"""
# #         }],
# #         "stream": False,
# #         "options": {
# #             "temperature": 0.7,
# #             "max_tokens": API_MAX_TOKENS
# #         }
# #     }
    
# #     return ollama_api_call(final_payload) or "Final generation failed"

# # @app.route('/process', methods=['POST'])
# # def handle_pdfs():
# #     """Main processing endpoint"""
# #     if 'files' not in request.files:
# #         return jsonify({'error': 'No files received'}), 400
    
# #     try:
# #         # File handling
# #         pdf_paths = []
# #         for file in request.files.getlist('files'):
# #             if file and allowed_file(file.filename):
# #                 filename = secure_filename(file.filename)
# #                 save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
# #                 file.save(save_path)
# #                 pdf_paths.append(save_path)
        
# #         if not pdf_paths:
# #             return jsonify({'error': 'No valid PDFs'}), 400
        
# #         # Text extraction
# #         combined_text = "\n\n".join(robust_text_extraction(p) for p in pdf_paths)
# #         if len(combined_text) < 100:
# #             return jsonify({'error': 'Insufficient text extracted'}), 400
        
# #         # Processing
# #         start_time = time.time()
# #         podcast_script = generate_podcast_script(combined_text)
# #         processing_time = time.time() - start_time
        
# #         return jsonify({
# #             'script': podcast_script,
# #             'processing_time': f"{processing_time:.2f}s",
# #             'source_files': [os.path.basename(p) for p in pdf_paths]
# #         })
    
# #     except Exception as e:
# #         logger.error(f"Processing failed: {str(e)}")
# #         return jsonify({'error': str(e)}), 500
    
# #     finally:
# #         # Cleanup
# #         for path in pdf_paths:
# #             try:
# #                 os.remove(path)
# #             except:
# #                 pass

# # if __name__ == '__main__':
# #     app.run(host='0.0.0.0', port=8000, debug=False)

# import os
# import requests
# from flask import Flask, jsonify, request
# from werkzeug.utils import secure_filename
# from PyPDF2 import PdfReader

# app = Flask(__name__)

# # Configuration
# UPLOAD_FOLDER = 'uploads'
# ALLOWED_EXTENSIONS = {'pdf'}
# MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
# CHUNK_SIZE = 2500  # Optimal for most LLM contexts
# OVERLAP = 300      # Maintain context between chunks

# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def extract_text_from_pdf(pdf_path):
#     """Extract text from PDF with error handling"""
#     text = ""
#     try:
#         with open(pdf_path, 'rb') as file:
#             reader = PdfReader(file)
#             for page in reader.pages:
#                 if page_text := page.extract_text():
#                     text += page_text + "\n"
#     except Exception as e:
#         print(f"PDF Extraction Error: {str(e)}")
#         raise
#     return text

# def chunk_text(text):
#     """Smart chunking with sentence boundary awareness"""
#     chunks = []
#     start = 0
#     text_length = len(text)
    
#     while start < text_length:
#         end = min(start + CHUNK_SIZE, text_length)
        
#         # Find nearest sentence boundary
#         while end > start and end < text_length and text[end] not in {'.', '!', '?', '\n\n'}:
#             end -= 1
            
#         if end == start:  # No natural break found
#             end = min(start + CHUNK_SIZE, text_length)
            
#         chunks.append(text[start:end].strip())
#         start = max(end - OVERLAP, start + 1)  # Ensure forward progress
    
#     return chunks

# def ollama_chat(messages, max_retries=3):
#     """Robust Ollama API communication with retries"""
#     for attempt in range(max_retries):
#         try:
#             response = requests.post(
#                 'http://localhost:11434/api/chat',
#                 json={
#                     "model": "llama3.2:latest",
#                     "messages": messages,
#                     "stream": False,
#                     "options": {"temperature": 0.5}
#                 },
#                 timeout=60
#             )
            
#             if response.status_code == 200:
#                 return response.json()['message']['content']
            
#             print(f"API Error (Attempt {attempt+1}): {response.text}")
            
#         except Exception as e:
#             print(f"Connection Error (Attempt {attempt+1}): {str(e)}")
            
#     return None

# def generate_podcast(text):
#     """Generate podcast script with chunked processing"""
#     chunks = chunk_text(text)
#     context = []
    
#     # System prompt to guide the model
#     system_prompt = {
#         "role": "user",
#         "content": """You are a research assistant. I will send research paper sections.
#                     Acknowledge with 'ACK' and store the information. Do not generate any other text."""
#     }
    
#     # Process chunks with context
#     for idx, chunk in enumerate(chunks):
#         messages = [system_prompt] + context[-2:]  # Keep last interaction
#         messages.append({
#             "role": "user",
#             "content": f"RESEARCH SECTION {idx+1}:\n{chunk}"
#         })
        
#         if response := ollama_chat(messages):
#             context.extend([
#                 messages[-1],
#                 {"role": "assistant", "content": response}
#             ])
#         else:
#             print(f"Failed to process chunk {idx+1}")
#             return "Error processing research content"
    
#     # Final generation prompt
#     final_prompt = {
#         "role": "user",
#         "content": """Generate a podcast script with this structure:
#         1. Introduction with context
#         2. Key findings and methodologies
#         3. Implications and future directions
#         4. Conclusion
        
#         Format as a natural dialogue between two researchers.
#         Use ONLY information from the provided research sections."""
#     }
    
#     return ollama_chat([system_prompt, final_prompt]) or "Generation failed"

# @app.route('/process_pdfs', methods=['POST'])
# def handle_pdfs():
#     if 'files' not in request.files:
#         return jsonify({'error': 'No files uploaded'}), 400
    
#     files = request.files.getlist('files')
#     pdf_paths = []
    
#     try:
#         for file in files:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#                 file.save(file_path)
#                 pdf_paths.append(file_path)
        
#         if not pdf_paths:
#             return jsonify({'error': 'No valid PDF files'}), 400
        
#         combined_text = "\n\n".join(extract_text_from_pdf(p) for p in pdf_paths)
#         podcast_script = generate_podcast(combined_text)
        
#         return jsonify({
#             'podcast_script': podcast_script,
#             'processed_files': [os.path.basename(p) for p in pdf_paths]
#         })
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#     finally:
#         for path in pdf_paths:
#             try:
#                 os.remove(path)
#             except:
#                 pass

# @app.route('/test_local', methods=['GET'])
# def test_local_pdfs():
#     """Test endpoint using ref1.pdf and ref2.pdf"""
#     test_files = ['ref1.pdf', 'ref2.pdf']
    
#     try:
#         # Validate test files exist
#         missing = [f for f in test_files if not os.path.exists(f)]
#         if missing:
#             return jsonify({'error': f'Missing test files: {", ".join(missing)}'}), 404
        
#         combined_text = "\n\n".join(extract_text_from_pdf(f) for f in test_files)
#         podcast_script = generate_podcast(combined_text)
        
#         return jsonify({
#             'podcast_script': podcast_script,
#             'processed_files': test_files
#         })
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8000, debug=True)


import os
import time
import logging
import requests
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 2500
OVERLAP = 300

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('PDFProcessor')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF with error handling"""
    logger.info(f"Extracting text from {os.path.basename(pdf_path)}")
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                if page_text := page.extract_text():
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF Extraction Error: {str(e)}")
        raise

def chunk_text(text):
    """Smart chunking with sentence boundary awareness"""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + CHUNK_SIZE, text_length)
        
        # Find nearest sentence boundary
        while end > start and end < text_length and text[end] not in {'.', '!', '?', '\n\n'}:
            end -= 1
            
        if end == start:  # No natural break found
            end = min(start + CHUNK_SIZE, text_length)
            
        chunks.append(text[start:end].strip())
        start = max(end - OVERLAP, start + 1)  # Ensure forward progress
    
    return chunks

def ollama_chat(messages, max_retries=3):
    """Robust Ollama API communication with retries"""
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            response = requests.post(
                'http://localhost:11434/api/chat',
                json={
                    "model": "llama3.2:latest",
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.5}
                },
                timeout=60
            )
            
            if response.status_code == 200:
                logger.debug(f"API call succeeded in {time.time() - start_time:.2f}s")
                return response.json()['message']['content']
            
            logger.warning(f"API Error (Attempt {attempt+1}): {response.text}")
            
        except Exception as e:
            logger.error(f"Connection Error (Attempt {attempt+1}): {str(e)}")
            
    return None

def process_single_pdf(text, pdf_name):
    """Process individual PDF and generate analysis"""
    logger.info(f"Starting processing for {pdf_name}")
    chunks = chunk_text(text)
    context = []
    
    # System prompt for individual analysis
    system_prompt = {
        "role": "system",
        "content": """Analyze research papers. For each section provide:
                    - Concise summary
                    - Key strengths/advantages
                    - Limitations/weaknesses
                    - 3-5 key findings
                    Format response with clear section headings"""
    }
    
    for idx, chunk in enumerate(chunks):
        logger.debug(f"Processing chunk {idx+1}/{len(chunks)} for {pdf_name}")
        messages = [system_prompt] + context[-2:]
        messages.append({
            "role": "user",
            "content": f"RESEARCH CONTENT SECTION {idx+1}:\n{chunk}"
        })
        
        response = ollama_chat(messages)
        if response:
            context.extend([
                messages[-1],
                {"role": "assistant", "content": response}
            ])
        else:
            logger.warning(f"Failed chunk {idx+1} for {pdf_name}")
    
    # Final analysis generation
    logger.info(f"Generating final analysis for {pdf_name}")
    final_prompt = {
        "role": "user",
        "content": "Compile comprehensive analysis with: Summary, Pros, Cons, Key Findings"
    }
    
    return ollama_chat([system_prompt, final_prompt]) or f"Analysis failed for {pdf_name}"

def generate_final_conclusion(analyses):
    """Generate final conclusion from all analyses"""
    logger.info("Generating final podcast script")
    system_prompt = {
        "role": "system",
        "content": """You're a podcast producer. Create an engaging script that:
                    - Compares/contrasts different research papers
                    - Highlights common findings and contradictions
                    - Discusses overall implications
                    Format as dialogue between two experts"""
    }
    
    user_prompt = {
        "role": "user",
        "content": "ANALYSES:\n" + "\n\n".join(
            f"Analysis {i+1}:\n{analysis}" 
            for i, analysis in enumerate(analyses)
        )
    }
    
    return ollama_chat([system_prompt, user_prompt]) or "Final conclusion generation failed"

@app.route('/process_pdfs', methods=['POST'])
def handle_pdfs():
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    pdf_paths = []
    individual_analyses = []
    
    try:
        # Process each PDF sequentially
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                pdf_paths.append(file_path)
                
                logger.info(f"Processing PDF: {filename}")
                try:
                    text = extract_text_from_pdf(file_path)
                    if not text:
                        logger.warning(f"No text extracted from {filename}")
                        continue
                        
                    analysis = process_single_pdf(text, filename)
                    individual_analyses.append(analysis)
                    logger.info(f"Completed processing for {filename}")
                    
                except Exception as e:
                    logger.error(f"Failed processing {filename}: {str(e)}")
                    continue
        
        if not individual_analyses:
            return jsonify({'error': 'No valid analyses generated'}), 400
        
        # Generate final conclusion
        final_script = generate_final_conclusion(individual_analyses)
        
        return jsonify({
            'podcast_script': final_script,
            'individual_analyses': individual_analyses,
            'processed_files': [os.path.basename(p) for p in pdf_paths]
        })
        
    except Exception as e:
        logger.error(f"Processing pipeline failed: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup files
        for path in pdf_paths:
            try:
                os.remove(path)
                logger.debug(f"Cleaned up file: {os.path.basename(path)}")
            except:
                pass

@app.route('/test_local', methods=['GET'])
def test_local_pdfs():
    """Test endpoint with verbose logging"""
    test_files = ['ref1.pdf', 'ref2.pdf']
    individual_analyses = []
    
    try:
        for filename in test_files:
            if not os.path.exists(filename):
                logger.error(f"Test file missing: {filename}")
                continue
                
            logger.info(f"Processing test file: {filename}")
            text = extract_text_from_pdf(filename)
            analysis = process_single_pdf(text, filename)
            individual_analyses.append(analysis)
        
        final_script = generate_final_conclusion(individual_analyses)
        
        return jsonify({
            'podcast_script': final_script,
            'individual_analyses': individual_analyses,
            'processed_files': test_files
        })
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)