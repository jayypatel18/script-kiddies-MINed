import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
  FormControl
} from '@mui/material';
import { AttachFile, Send, Delete, VolumeUp } from '@mui/icons-material';

const App = () => {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [output, setOutput] = useState('');
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [voices, setVoices] = useState([]);
  const [ttsLanguage, setTtsLanguage] = useState('en-US');
  
  // PDF Dropzone
  const onDrop = useCallback(acceptedFiles => {
    const pdfFiles = acceptedFiles.filter(file => file.type === 'application/pdf');
    setFiles(prev => [...prev, ...pdfFiles.map(file => 
      Object.assign(file, { preview: URL.createObjectURL(file) })
    )]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {'application/pdf': ['.pdf']},
    multiple: true
  });

  // Text-to-Speech Setup
  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => setVoices(window.speechSynthesis.getVoices());
      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    }
  }, []);

  const speak = (text) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = ttsLanguage;
    window.speechSynthesis.speak(utterance);
  };

  // API Submission
  const handleSubmit = async () => {
    if (!inputText && files.length === 0) return;

    const formData = new FormData();
    files.forEach(file => formData.append('pdfs', file));
    formData.append('question', inputText);

    try {
      setLoading(true);
      const response = await axios.post('http://localhost:5000/api/process', formData);
      setOutput(response.data.result);
      speak(response.data.result);
    } catch (error) {
      console.error(error);
      setOutput(t('error_processing'));
    } finally {
      setLoading(false);
    }
  };

  const removeFile = (fileName) => {
    setFiles(files.filter(file => file.name !== fileName));
  };

  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>{t('title')}</Typography>
          <FormControl variant="standard" sx={{ minWidth: 120, color: 'white' }}>
            <InputLabel sx={{ color: 'white' }}>{t('language')}</InputLabel>
            <Select
              value={localStorage.getItem('i18nextLng') || 'en'}
              onChange={(e) => i18n.changeLanguage(e.target.value)}
              sx={{ color: 'white' }}
            >
              <MenuItem value="en">English</MenuItem>
              <MenuItem value="es">Español</MenuItem>
            </Select>
          </FormControl>
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
            placeholder={t('output_placeholder')}
          />
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl fullWidth>
              <InputLabel>{t('tts_language')}</InputLabel>
              <Select
                value={ttsLanguage}
                onChange={(e) => setTtsLanguage(e.target.value)}
                label={t('tts_language')}
              >
                {voices.map(voice => (
                  <MenuItem key={voice.lang} value={voice.lang}>
                    {voice.name} ({voice.lang})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <IconButton onClick={() => speak(output)} disabled={!output}>
              <VolumeUp />
            </IconButton>
          </Box>
        </Paper>

        {/* Attached Files */}
        {files.length > 0 && (
          <Paper sx={{ mb: 2, p: 2 }}>
            <Typography variant="subtitle1">{t('attached_files')}:</Typography>
            <List dense>
              {files.map(file => (
                <ListItem key={file.name} secondaryAction={
                  <IconButton edge="end" onClick={() => removeFile(file.name)}>
                    <Delete />
                  </IconButton>
                }>
                  <ListItemIcon>
                    <AttachFile />
                  </ListItemIcon>
                  <ListItemText primary={file.name} />
                </ListItem>
              ))}
            </List>
          </Paper>
        )}

        {/* Drag & Drop Zone */}
        <Paper {...getRootProps()} sx={{ 
          p: 4, 
          mb: 2, 
          border: '2px dashed',
          borderColor: isDragActive ? 'primary.main' : 'text.secondary',
          backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
          textAlign: 'center',
          cursor: 'pointer'
        }}>
          <input {...getInputProps()} />
          <AttachFile fontSize="large" />
          <Typography>{t('drag_drop_files')}</Typography>
          <Typography variant="caption">({t('multiple_files_allowed')})</Typography>
        </Paper>

        {/* Input Section */}
        <Grid container spacing={2} alignItems="center">
          <Grid item xs>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={t('input_placeholder')}
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
              {t('send_button')}
            </Button>
          </Grid>
        </Grid>

        {loading && <LinearProgress sx={{ mt: 2 }} />}
      </Container>
    </div>
  );
};

export default App;