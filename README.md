# VoiceCraft Studio 🎙️

VoiceCraft Studio is a modern web application that transforms research papers and PDF documents into engaging podcast-style audio content. Built with React for the frontend and Python Flask for the backend, it offers a seamless experience for converting academic content into accessible audio formats.

## Features

- 📄 Multiple PDF upload support
- 🎨 Customizable content styles (concise, elaborate, balanced, formal, casual, professional)
- ⏱️ Flexible podcast duration options
- 🔊 Real-time audio preview
- 💾 MP3 download capability
- 📱 Responsive design for all devices

## Tech Stack

### Frontend
- React
- Material-UI (MUI)
- Eleven Labs API for text-to-speech
- Axios for API calls
- React-Dropzone for file handling

### Backend
- Python Flask
- PyTesseract for OCR
- PDF2Image for PDF processing
- OpenAI's Mistral model for text processing
- CORS for cross-origin support

## Prerequisites

Before you begin, ensure you have installed:
- Node.js (v14 or higher)
- Python (v3.8 or higher)
- Tesseract OCR
- Poppler (for PDF processing)

## Environment Variables

### Frontend (.env)
```
VITE_ELEVEN_LABS_API_KEY=your_eleven_labs_api_key
VITE_ELEVEN_LABS_VOICE_ID=your_voice_id
```

### Backend (.env)
```
FLASK_APP=app.py
FLASK_ENV=development
```

## Installation

### Frontend Setup

1. Clone the repository
```bash
git clone <repository-url>
cd voicecraft-studio
```

2. Install dependencies
```bash
npm install
```

3. Start the development server
```bash
npm run dev
```

### Backend Setup

1. Navigate to the backend directory
```bash
cd backend
```

2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies
```bash
pip install -r requirements.txt
```

4. Start the Flask server
```bash
python real_server.py
```

## Usage

1. Access the application at `http://localhost:5173` (or your Vite default port)
2. Upload PDF files using the drag-and-drop interface
3. Select your desired content style and podcast duration
4. Click "Generate Podcast" to process your files
5. Use the audio controls to preview the generated content
6. Download the final audio as MP3

## API Endpoints

### POST /generate
Processes PDF files and generates podcast script
- Request: Multipart form data
  - `pdfs`: PDF files (multiple)
  - `contentStyle`: String
  - `duration`: String
- Response: JSON with generated script and metadata

### GET /get_summary/:result_id
Retrieves a previously generated summary
- Parameters: result_id (UUID)
- Response: JSON with summary data

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details

## Acknowledgments

- Eleven Labs for text-to-speech API
- Material-UI for the component library
- Mistral AI for the language model
- All contributors and maintainers

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
