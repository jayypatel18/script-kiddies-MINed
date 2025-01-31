import { useState, useEffect, useCallback, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
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
  TextField
} from '@mui/material';
import { AttachFile, Send, Delete, VolumeUp, PlayArrow, Pause } from '@mui/icons-material';

const CHROME_VOICES = {
  male: {
    name: 'Google US English Male',
    fallbackNames: ['Microsoft David - English (United States)', 'English Male'],
    config: {
      basePitch: 0.9,
      baseRate: 1.0,
      question: { pitch: 1.25, rate: 1.15, pause: 800 },
      exclamation: { pitch: 1.35, rate: 1.2, pause: 600 },
      statement: { pitch: 0.85, rate: 0.95, pause: 1000 }
    }
  }
};

const App = () => {
  const [files, setFiles] = useState([]);
  const [output, setOutput] = useState('Hello! How are you today?');
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [voicesReady, setVoicesReady] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [currentSentence, setCurrentSentence] = useState(-1);
  const [isPaused, setIsPaused] = useState(false);
  const [podcastLength, setPodcastLength] = useState(null);
  const [contentStyle, setContentStyle] = useState(null);

  const sentences = useMemo(() => 
    output.match(/[^.!?]+[.!?]|[^.!?]+$/g) || []
  , [output]);

  useEffect(() => {
    const initializeVoices = () => {
      if (!window.speechSynthesis) {
        setSpeechError('Speech synthesis not supported');
        return;
      }

      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
          setVoicesReady(true);
          window.speechSynthesis.onvoiceschanged = null;
        }
      };

      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    };

    initializeVoices();
  }, []);

  useEffect(() => {
    if (currentSentence === -1) {
      setIsPaused(false);
    }
  }, [currentSentence]);

  const getVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    const voiceConfig = CHROME_VOICES.male;
    
    return voices.find(v => v.name === voiceConfig.name) ||
           voices.find(v => voiceConfig.fallbackNames.includes(v.name)) ||
           voices.find(v => v.lang === 'en-US' && v.name.includes('Male')) ||
           voices.find(v => v.lang === 'en-US');
  };

  const speakText = (text) => {
    try {
      if (!text) return;
      window.speechSynthesis.cancel();
      setCurrentSentence(-1);
      setIsPaused(false);

      const voice = getVoice();
      if (!voice) {
        setSpeechError('No voices available - try refreshing');
        return;
      }

      const processSegment = (index = 0) => {
        if (index >= sentences.length) return;
        setCurrentSentence(index);

        const sentence = sentences[index].trim();
        if (!sentence) return processSegment(index + 1);

        const utterance = new SpeechSynthesisUtterance(sentence);
        utterance.voice = voice;
        utterance.lang = 'en-US';

        const lastChar = sentence.slice(-1);
        const config = CHROME_VOICES.male.config;
        switch(lastChar) {
          case '?': Object.assign(utterance, config.question); break;
          case '!': Object.assign(utterance, config.exclamation); break;
          default: Object.assign(utterance, config.statement);
        }

        utterance.onend = () => {
          setTimeout(() => processSegment(index + 1), 
            lastChar === '?' ? config.question.pause :
            lastChar === '!' ? config.exclamation.pause :
            config.statement.pause
          );
        };

        window.speechSynthesis.speak(utterance);
      };

      processSegment(0);
    } catch (error) {
      console.error('Speech error:', error);
      setSpeechError('Error generating speech');
    }
  };

  const togglePlayPause = () => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setIsPaused(false);
    } else {
      window.speechSynthesis.pause();
      setIsPaused(true);
    }
  };

  const handleLengthSelection = (length) => {
    setPodcastLength(current => current === length ? null : length);
  };

  const handleContentStyle = (style) => {
    setContentStyle(current => current === style ? null : style);
  };

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

  const handleSubmit = async () => {
    if (!inputText && files.length === 0) return;

    try {
      setLoading(true);
      await new Promise(resolve => setTimeout(resolve, 500));
      const result = inputText || "Please provide text or upload a PDF.";
      setOutput(result);
    } catch (error) {
      console.error(error);
      setOutput('Error processing request');
    } finally {
      setLoading(false);
    }
  };

  const removeFile = (fileName) => {
    setFiles(files.filter((file) => file.name !== fileName));
  };

  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Chrome Voice Assistant
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ mt: 4, height: '80vh', display: 'flex', flexDirection: 'column' }}>
        {speechError && (
          <Paper sx={{ p: 2, mb: 2, bgcolor: 'error.light' }}>
            <Typography color="error">{speechError}</Typography>
          </Paper>
        )}

        <Paper sx={{ flex: 1, mb: 2, p: 2, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ 
            flex: 1,
            p: 2,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: '4px',
            whiteSpace: 'pre-wrap',
            mb: 2,
            overflow: 'auto'
          }}>
            {sentences.map((sentence, index) => (
              <span
                key={index}
                style={{
                  backgroundColor: index === currentSentence ? 'lightgreen' : 'transparent',
                  display: 'inline-block',
                  margin: '2px 0',
                  transition: 'background-color 0.3s ease',
                }}
              >
                {sentence}
              </span>
            ))}
          </Box>
          
          {/* Control Section */}
          <Box sx={{ 
            pt: 2,
            borderTop: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          }}>
            {/* Playback Controls (Top) */}
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
              <Button
                variant="contained"
                onClick={() => speakText(output)}
                disabled={!voicesReady || !output}
                startIcon={<PlayArrow />}
                size="small"
              >
                Play
              </Button>
              <Button
                variant="contained"
                onClick={togglePlayPause}
                disabled={!voicesReady || !output || currentSentence === -1}
                startIcon={isPaused ? <PlayArrow /> : <Pause />}
                size="small"
              >
                {isPaused ? 'Resume' : 'Pause'}
              </Button>
            </Box>

            {/* Podcast Length Buttons */}
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
              {['small', 'moderate', 'lengthy'].map((length) => (
                <Button
                  key={length}
                  variant={podcastLength === length ? 'contained' : 'outlined'}
                  onClick={() => handleLengthSelection(length)}
                  color="secondary"
                  size="small"
                  sx={{ textTransform: 'none' }}
                >
                  {length.charAt(0).toUpperCase() + length.slice(1)}
                </Button>
              ))}
            </Box>

            {/* Content Style Buttons */}
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
              <Button
                variant={contentStyle === 'concise' ? 'contained' : 'outlined'}
                onClick={() => handleContentStyle('concise')}
                color="primary"
                size="small"
                sx={{ textTransform: 'none' }}
              >
                Concise
              </Button>
              <Button
                variant={contentStyle === 'elaborate' ? 'contained' : 'outlined'}
                onClick={() => handleContentStyle('elaborate')}
                color="primary"
                size="small"
                sx={{ textTransform: 'none' }}
              >
                Elaborate
              </Button>
            </Box>
          </Box>
        </Paper>

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
          <Typography>Drag PDFs here</Typography>
          <Typography variant="caption">(Maximum 5 PDF files)</Typography>
        </Paper>

        <Grid container spacing={2} alignItems="center">
          <Grid item xs>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type or upload PDFs..."
              variant="outlined"
              sx={{ '& .MuiInputBase-root': { alignItems: 'flex-start' } }}
            />
          </Grid>
          <Grid item>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              disabled={loading}
              startIcon={<Send />}
              sx={{ height: '56px' }}
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