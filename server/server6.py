import os
import requests
from flask import Flask, jsonify, request
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

app = Flask(__name__)

# Configuration
API_URL = "https://api.groq.com/v1/chat/completions"  # Hypothetical ChatGroq API endpoint
HEADERS = {
    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",  # Replace with your actual ChatGroq API key
    "Content-Type": "application/json"
}
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Increased to 100MB to handle multiple PDFs

# Updated models with proper chat templates for ChatGroq
AGENTS = {
    "extractor": "groq-extractor-model",
    "analyst": "groq-analyst-model",
    "narrator": "groq-narrator-model"
}

# In-memory storage for results
results_storage = {}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def format_prompt(agent_type, prompt):
    """
    Format prompts according to ChatGroq's model requirements.
    Adjust the formatting based on the agent type.
    """
    if agent_type == "extractor":
        return f"Extract the following information:\n{prompt}"
    elif agent_type == "analyst":
        return f"Analyze the content:\n{prompt}"
    elif agent_type == "narrator":
        return f"Create a podcast script based on the analysis:\n{prompt}"
    return prompt

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a given PDF file.
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                if page_text := page.extract_text():
                    text += page_text + "\n"
    except Exception as e:
        print(f"PDF Error ({pdf_path}): {str(e)}")
    return text

def chunk_text(text, chunk_size=800):
    """
    Split text into chunks of a specified word count.
    """
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def query_agent(prompt, agent_type, max_retries=5):
    """
    Query ChatGroq's API with the given prompt and agent type.
    Implements retry logic for handling transient errors.
    """
    formatted_prompt = format_prompt(agent_type, prompt)
    payload = {
        "model": AGENTS[agent_type],
        "messages": [
            {"role": "user", "content": formatted_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.5
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload)
            if response.status_code == 200:
                result = response.json()
                # Assuming the API returns a JSON with 'choices' similar to OpenAI
                return result['choices'][0]['message']['content'].strip()
            elif response.status_code == 429:
                # Rate limit exceeded, wait and retry
                wait_time = (attempt + 1) * 10
                print(f"Rate limit exceeded. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif response.status_code == 503:
                # Service unavailable, wait and retry
                wait_time = (attempt + 1) * 10
                print(f"Service unavailable. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"API Error ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            print(f"Connection Error: {str(e)}. Retrying...")
            time.sleep(5)
    return None

def process_chunk(chunk, chunk_num, total_chunks):
    """
    Process a single text chunk by extracting key information and analyzing it.
    """
    # Extraction Agent
    extraction_prompt = f"Extract key information from research paper chunk {chunk_num}/{total_chunks}:\n{chunk}\n\nIdentify:\n- Research objectives\n- Methodology\n- Key findings\n- Limitations\n\nUse clear bullet points."
    extracted = query_agent(extraction_prompt, "extractor") or "Extraction failed"

    # Analysis Agent
    analysis_prompt = f"Analyze this research content:\n{extracted}\n\nProvide critical analysis of:\n1. Methodology validity\n2. Significance of findings\n3. Potential biases\n\nUse academic tone."
    analysis = query_agent(analysis_prompt, "analyst") or "Analysis failed"

    return f"CHUNK {chunk_num}:\n{extracted}\n\nANALYSIS:\n{analysis}"

def generate_podcast_script(processed_chunks):
    """
    Generate a podcast script based on the processed chunks.
    """
    combined_analysis = "\n".join(processed_chunks)
    narrator_prompt = f"Create a podcast script from this research analysis:\n{combined_analysis}\n\nFormat:\nHost 1: [Introduces topic]\nHost 2: [Explains methodology]\nHost 1: [Discusses findings]\nHost 2: [Critical analysis]\nBoth: [Conclusion]\n\nUse natural dialogue, avoid jargon, keep it engaging."
    script = query_agent(narrator_prompt, "narrator")
    return script or "Script generation failed"

@app.route('/process_local', methods=['POST'])
def process_local_pdfs():
    """
    Endpoint to process multiple local PDF files.
    """
    pdf_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.startswith('ref') and f.endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'No PDF files found'}), 404

    try:
        combined_text = ""
        for pdf in pdf_files:
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf)
            text = extract_text_from_pdf(pdf_path)
            combined_text += f"\n\n--- {pdf} ---\n\n" + text  # Separating content by PDF

        chunks = chunk_text(combined_text)

        processed_chunks = []
        # Using ThreadPoolExecutor to handle multiple chunks concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_chunk, chunk, i+1, len(chunks)) for i, chunk in enumerate(chunks)]
            for future in futures:
                result = future.result()
                if result:
                    processed_chunks.append(result)
                print(f"Processed chunk {futures.index(future)+1}/{len(futures)}")

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