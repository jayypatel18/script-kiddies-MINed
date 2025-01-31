import os
import requests
from flask import Flask, jsonify, request
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import uuid
import time

load_dotenv()

app = Flask(__name__)

# Configuration
API_URL = "https://api-inference.huggingface.co/models/"
HEADERS = {"Authorization": f"Bearer {os.getenv('HF_KEY')}"}
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Updated models with proper chat templates
AGENTS = {
    "extractor": "mistralai/Mistral-7B-Instruct-v0.2",
    "analyst": "meta-llama/Meta-Llama-3-8B-Instruct",
    "narrator": "HuggingFaceH4/zephyr-7b-beta"
}

results_storage = {}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def format_prompt(model_type, prompt):
    """Format prompts according to model requirements"""
    if "mistral" in model_type.lower():
        return f"[INST] {prompt} [/INST]"
    elif "llama-3" in model_type.lower():
        return f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>
        {prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    elif "zephyr" in model_type.lower():
        return f"<|system|>\n</s>\n<|user|>\n{prompt}</s>\n<|assistant|>"
    return prompt

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                if page_text := page.extract_text():
                    text += page_text + "\n"
    except Exception as e:
        print(f"PDF Error: {str(e)}")
    return text

def chunk_text(text, chunk_size=800):
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def query_agent(prompt, agent_type, max_retries=5):
    formatted_prompt = format_prompt(AGENTS[agent_type], prompt)
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL + AGENTS[agent_type],
                headers=HEADERS,
                json={
                    "inputs": formatted_prompt,
                    "parameters": {
                        "max_new_tokens": 500,
                        "temperature": 0.5,
                        "return_full_text": False,
                        "do_sample": True
                    }
                }
            )
            
            if response.status_code == 200:
                # Handle different response formats
                result = response.json()
                if isinstance(result, list) and 'generated_text' in result[0]:
                    return result[0]['generated_text']
                return result.get('generated_text', '')
            
            elif response.status_code == 503:
                wait_time = (attempt + 1) * 10
                print(f"Model loading, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            print(f"API Error ({response.status_code}): {response.text}")
            return None
            
        except Exception as e:
            print(f"Connection Error: {str(e)}")
            time.sleep(5)
    
    return None

def process_chunk(chunk, chunk_num, total_chunks):
    # Extraction Agent
    extraction_prompt = f"""Extract key information from research paper chunk {chunk_num}/{total_chunks}:
    {chunk}
    
    Identify:
    - Research objectives
    - Methodology
    - Key findings
    - Limitations
    
    Use clear bullet points."""
    
    extracted = query_agent(extraction_prompt, "extractor") or "Extraction failed"
    
    # Analysis Agent
    analysis_prompt = f"""Analyze this research content:
    {extracted}
    
    Provide critical analysis of:
    1. Methodology validity
    2. Significance of findings
    3. Potential biases
    
    Use academic tone."""
    
    analysis = query_agent(analysis_prompt, "analyst") or "Analysis failed"
    
    return f"CHUNK {chunk_num}:\n{extracted}\n\nANALYSIS:\n{analysis}"

def generate_podcast_script(processed_chunks):
    narrator_prompt = f"""Create a podcast script from this research analysis:
    {" ".join(processed_chunks)}
    
    Format:
    Host 1: [Introduces topic]
    Host 2: [Explains methodology]
    Host 1: [Discusses findings]
    Host 2: [Critical analysis]
    Both: [Conclusion]
    
    Use natural dialogue, avoid jargon, keep it engaging."""
    
    script = query_agent(narrator_prompt, "narrator")
    return script or "Script generation failed"

@app.route('/process_local', methods=['GET'])
def process_local_pdfs():
    pdf_files = [f for f in os.listdir() if f.startswith('ref') and f.endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No PDF files found'}), 404

    try:
        combined_text = "\n\n".join(extract_text_from_pdf(f) for f in pdf_files)
        chunks = chunk_text(combined_text)
        
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            processed = process_chunk(chunk, i+1, len(chunks))
            processed_chunks.append(processed)
            print(f"Processed chunk {i+1}/{len(chunks)}")
            
        podcast_script = generate_podcast_script(processed_chunks)
        
        # Clean up script output
        cleaned_script = "\n".join([line.strip() for line in podcast_script.split("\n") if line.strip()])
        
        result_id = str(uuid.uuid4())
        results_storage[result_id] = {
            'script': cleaned_script,
            'files': pdf_files
        }
        
        return jsonify({
            'result_id': result_id,
            'processed_files': pdf_files,
            'script': cleaned_script
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)