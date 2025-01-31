import { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  TextField,
  Button,
  IconButton,
  Grid,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  Box,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
} from '@mui/material';
import { AttachFile, Send, Delete, VolumeUp } from '@mui/icons-material';

const App = () => {
  // States
  const [files, setFiles] = useState([]);
  const [output, setOutput] = useState('How are you?');
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [selectedLangCode, setSelectedLangCode] = useState('en');

  // Translation options (language codes must match LibreTranslate's codes)
  const TRANSLATION_OPTIONS = [
    { code: 'en', label: 'English', voiceName: 'Google US English' },
    { code: 'es', label: 'Spanish', voiceName: 'Google español' },
    { code: 'hi', label: 'Hindi', voiceName: 'Google हिन्दी' },
    { code: 'fr', label: 'French', voiceName: 'Google français' },
  ];

  // PDF Dropzone
  const onDrop = useCallback((acceptedFiles) => {
    const pdfFiles = acceptedFiles.filter((file) => file.type === 'application/pdf');
    setFiles((prev) => [
      ...prev,
      ...pdfFiles.map((file) => Object.assign(file, { preview: URL.createObjectURL(file) })),
    ]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  });

  // Load browser voices
  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        setAvailableVoices(voices);
      };
      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    }
  }, []);

  // Free translation using LibreTranslate's public API
  const translateText = async (text, targetLang) => {
    try {
      const response = await axios.post(
        'https://libretranslate.com/translate',
        {
          q: text,
          source: 'en', // Input text is assumed to be English
          target: targetLang,
          format: 'text',
        },
        { headers: { 'Content-Type': 'application/json' } }
      );
      return response.data.translatedText;
    } catch (error) {
      console.error('Translation error:', error);
      return text; // Fallback to original text
    }
  };

  // Speak translated text
  const speakTranslatedText = async (text, targetLang) => {
    if (!text) return;

    const translated = await translateText(text, targetLang);
    setOutput(translated);

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(translated);

      // Find matching voice
      const voice = availableVoices.find((v) => 
        v.lang.startsWith(targetLang) || 
        v.name.includes(TRANSLATION_OPTIONS.find(l => l.code === targetLang)?.label)
      );

      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = targetLang;
      }

      window.speechSynthesis.speak(utterance);
    }
  };

  // Submit handler (PDF processing would need your own backend)
  const handleSubmit = async () => {
    if (!inputText && files.length === 0) return;

    // Simulated API call - replace with actual PDF processing
    try {
      setLoading(true);
      // This is where you'd send PDFs to your backend
      // For now, we'll just use the input text directly
      const result = inputText;
      setOutput(result);
      speakTranslatedText(result, selectedLangCode);
    } catch (error) {
      console.error(error);
      setOutput('Error processing request');
    } finally {
      setLoading(false);
    }
  };

  // Remove file
  const removeFile = (fileName) => {
    setFiles(files.filter((file) => file.name !== fileName));
  };

  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Free Multilingual PDF Assistant
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ mt: 4, height: '80vh', display: 'flex', flexDirection: 'column' }}>
        {/* Output Section */}
        <Paper sx={{ flex: 1, mb: 2, p: 2, overflow: 'auto' }}>
          <TextField
            fullWidth
            multiline
            rows={12}
            value={output}
            variant="outlined"
            InputProps={{ readOnly: true }}
            placeholder="Translated response will appear here..."
          />
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl fullWidth>
              <InputLabel>Output Language</InputLabel>
              <Select
                value={selectedLangCode}
                onChange={(e) => setSelectedLangCode(e.target.value)}
                label="Output Language"
              >
                {TRANSLATION_OPTIONS.map((option) => (
                  <MenuItem key={option.code} value={option.code}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <IconButton
              onClick={() => speakTranslatedText(output, selectedLangCode)}
              disabled={!output}
            >
              <VolumeUp />
            </IconButton>
          </Box>
        </Paper>

        {/* Attached Files */}
        {files.length > 0 && (
          <Paper sx={{ mb: 2, p: 2 }}>
            <Typography variant="subtitle1">Attached PDFs:</Typography>
            <List dense>
              {files.map((file) => (
                <ListItem
                  key={file.name}
                  secondaryAction={
                    <IconButton edge="end" onClick={() => removeFile(file.name)}>
                      <Delete />
                    </IconButton>
                  }
                >
                  <ListItemIcon>
                    <AttachFile />
                  </ListItemIcon>
                  <ListItemText primary={file.name} />
                </ListItem>
              ))}
            </List>
          </Paper>
        )}

        {/* PDF Upload Zone */}
        <Paper
          {...getRootProps()}
          sx={{
            p: 4,
            mb: 2,
            border: '2px dashed',
            borderColor: isDragActive ? 'primary.main' : 'text.secondary',
            backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
            textAlign: 'center',
            cursor: 'pointer',
          }}
        >
          <input {...getInputProps()} />
          <AttachFile fontSize="large" />
          <Typography>Drag & drop PDFs here</Typography>
          <Typography variant="caption">(Max 5 files, PDF only)</Typography>
        </Paper>

        {/* Text Input */}
        <Grid container spacing={2} alignItems="center">
          <Grid item xs>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Or type your text here..."
              variant="outlined"
            />
          </Grid>
          <Grid item>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              disabled={loading}
              startIcon={<Send />}
            >
              Process
            </Button>
          </Grid>
        </Grid>

        {loading && <LinearProgress sx={{ mt: 2 }} />}
      </Container>
    </div>
  );
};

export default App;