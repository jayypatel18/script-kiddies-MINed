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
  TextField,
  Chip,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { 
  AttachFile, 
  Send, 
  Delete, 
  PlayArrow, 
  Pause, 
  FiberManualRecord,
  VolumeUp 
} from '@mui/icons-material';
import { styled, alpha, keyframes } from '@mui/material/styles';

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

const pulse = keyframes`
  0% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1); opacity: 0.8; }
`;

const VoiceActivityIndicator = styled(Box)(({ theme, active }) => ({
  width: 24,
  height: 24,
  borderRadius: '50%',
  backgroundColor: active ? theme.palette.success.main : theme.palette.grey[500],
  animation: active ? `${pulse} 1s infinite` : 'none',
  transition: 'background-color 0.3s ease',
}));

const GradientAppBar = styled(AppBar)(({ theme }) => ({
  background: `linear-gradient(45deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 100%)`,
  boxShadow: 'none',
}));

const AnimatedPaper = styled(Paper)(({ theme }) => ({
  transition: 'transform 0.2s, box-shadow 0.2s',
  borderRadius: '16px',
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: theme.shadows[6]
  }
}));

const StyledDropzone = styled(Paper)(({ theme, isdragactive }) => ({
  backgroundColor: isdragactive === 'true' ? alpha(theme.palette.primary.light, 0.1) : theme.palette.background.paper,
  border: `2px dashed ${alpha(theme.palette.primary.main, 0.5)}`,
  cursor: 'pointer',
  '&:hover': {
    borderColor: theme.palette.primary.main,
    backgroundColor: alpha(theme.palette.primary.light, 0.05)
  }
}));

const ProgressIndicator = styled(LinearProgress)(({ theme }) => ({
  height: 8,
  borderRadius: 4,
  backgroundColor: alpha(theme.palette.primary.main, 0.1),
  '& .MuiLinearProgress-bar': {
    borderRadius: 4,
    backgroundColor: theme.palette.primary.main
  }
}));

const PlayButton = styled(Button)(({ theme }) => ({
  minWidth: 120,
  borderRadius: '28px',
  padding: '12px 24px',
  textTransform: 'none',
  fontWeight: 600,
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  [theme.breakpoints.down('sm')]: {
    minWidth: '100%',
    padding: '10px 20px'
  },
  '&:hover': {
    transform: 'scale(1.05)'
  }
}));

const App = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [files, setFiles] = useState([]);
  const [output, setOutput] = useState('');
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [voicesReady, setVoicesReady] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [currentSentence, setCurrentSentence] = useState(-1);
  const [isPaused, setIsPaused] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [podcastLength, setPodcastLength] = useState(null);
  const [contentStyle, setContentStyle] = useState(null);
  const [validationError, setValidationError] = useState('');

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
      setIsSpeaking(false);
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
      setIsSpeaking(true);

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

        utterance.onerror = () => {
          setIsSpeaking(false);
          setCurrentSentence(-1);
        };

        window.speechSynthesis.speak(utterance);
      };

      processSegment(0);
    } catch (error) {
      console.error('Speech error:', error);
      setSpeechError('Error generating speech');
      setIsSpeaking(false);
    }
  };

  const validateSelections = () => {
    if (!podcastLength || !contentStyle) {
      setValidationError('Please select both duration and content style before playing');
      return false;
    }
    setValidationError('');
    return true;
  };

  const handlePlayPause = () => {
    if (!validateSelections()) return;
    
    if (isSpeaking) {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        setIsPaused(false);
      } else {
        window.speechSynthesis.pause();
        setIsPaused(true);
      }
    } else {
      speakText(output);
    }
  };

  const handleStop = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setCurrentSentence(-1);
    setIsPaused(false);
  };

  const handleLengthSelection = (length) => {
    setPodcastLength(length);
    setValidationError('');
  };

  const handleContentStyle = (style) => {
    setContentStyle(style);
    setValidationError('');
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
      const result = inputText || "PDF content processed";
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

  const hasContent = output.length > 0;

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <GradientAppBar position="sticky">
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <VolumeUp sx={{ mr: 2, fontSize: 32, color: 'white' }} />
            <Box>
              <Typography variant="h6" fontWeight="700" color="white">
                VoiceCraft Studio
              </Typography>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                Transform text into natural sounding speech
              </Typography>
            </Box>
          </Box>
        </Toolbar>
      </GradientAppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Grid container spacing={4}>
          <Grid item xs={12} md={5}>
            <AnimatedPaper elevation={3} sx={{ p: 3 }}>
              <Typography variant="subtitle1" fontWeight="600" mb={2}>
                Input Content
              </Typography>
              
              <StyledDropzone
                {...getRootProps()}
                isdragactive={isDragActive.toString()}
                sx={{ p: isMobile ? 2 : 4, mb: 3, borderRadius: 3 }}
              >
                <input {...getInputProps()} />
                <Box sx={{ textAlign: 'center', color: 'primary.main' }}>
                  <AttachFile sx={{ fontSize: 40, mb: 1 }} />
                  <Typography variant="body2" fontWeight="500">
                    Drag & drop PDF files
                  </Typography>
                  
                </Box>
              </StyledDropzone>

              {files.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="caption" fontWeight="500" color="text.secondary">
                    Attached files:
                  </Typography>
                  <List dense>
                    {files.map((file) => (
                      <ListItem
                        key={file.name}
                        sx={{
                          borderRadius: 2,
                          bgcolor: 'action.hover',
                          mb: 1,
                          pr: 8
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <AttachFile fontSize="small" />
                        </ListItemIcon>
                        <ListItemText
                          primary={file.name}
                          primaryTypographyProps={{ variant: 'caption' }}
                        />
                        <IconButton
                          size="small"
                          onClick={() => removeFile(file.name)}
                          sx={{ position: 'absolute', right: 8 }}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              <TextField
                fullWidth
                multiline
                minRows={4}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Or type/paste your text here..."
                variant="outlined"
                sx={{
                  mb: 3,
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                    bgcolor: 'background.paper'
                  }
                }}
              />

              <Button
                fullWidth
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || (!inputText && files.length === 0)}
                startIcon={<Send />}
                sx={{
                  height: 48,
                  borderRadius: 2,
                  fontWeight: 600,
                  textTransform: 'none'
                }}
              >
                Generate Podcast
              </Button>

              {loading && <ProgressIndicator sx={{ mt: 2 }} />}
            </AnimatedPaper>
          </Grid>

          <Grid item xs={12} md={7}>
            <AnimatedPaper elevation={3} sx={{ p: 3, height: '100%' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="subtitle1" fontWeight="600">
                  Podcast Preview
                </Typography>
                {hasContent && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <VoiceActivityIndicator 
                      active={isSpeaking && !isPaused} 
                    />
                    <Typography variant="caption" color="text.secondary">
                      {isSpeaking ? (isPaused ? 'Paused' : 'Live') : 'Idle'}
                    </Typography>
                  </Box>
                )}
              </Box>

              <Paper
                variant="outlined"
                sx={{
                  p: 3,
                  mb: 3,
                  borderRadius: 3,
                  bgcolor: 'background.paper',
                  height: isMobile ? 300 : 400,
                  overflow: 'auto',
                  minHeight: 200
                }}
              >
                {hasContent ? (
                  sentences.map((sentence, index) => (
                    <Box
                      key={index}
                      sx={{
                        p: 1.5,
                        mb: 1,
                        borderRadius: 2,
                        bgcolor: index === currentSentence ? 'primary.light' : 'transparent',
                        transition: 'background-color 0.3s ease'
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: index === currentSentence ? 600 : 400,
                          color: index === currentSentence ? 'primary.dark' : 'text.primary'
                        }}
                      >
                        {sentence}
                      </Typography>
                    </Box>
                  ))
                ) : (
                  <Box sx={{ 
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'text.secondary'
                  }}>
                    <Typography variant="body2">
                      Generate content to see preview
                    </Typography>
                  </Box>
                )}
              </Paper>

              {hasContent && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {validationError && (
                    <Typography color="error" variant="caption">
                      {validationError}
                    </Typography>
                  )}

                  <Box sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 2,
                    flexDirection: isMobile ? 'column' : 'row'
                  }}>
                    <PlayButton
                      variant="contained"
                      onClick={handlePlayPause}
                      disabled={!voicesReady}
                      startIcon={isPaused ? <PlayArrow /> : <Pause />}
                    >
                      {isSpeaking ? (isPaused ? 'Resume' : 'Pause') : 'Play'}
                    </PlayButton>

                    <Button
                      variant="outlined"
                      onClick={handleStop}
                      disabled={!isSpeaking}
                      sx={{ 
                        borderRadius: '28px', 
                        textTransform: 'none',
                        width: isMobile ? '100%' : 'auto'
                      }}
                    >
                      Stop
                    </Button>
                  </Box>

                  <Box sx={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    gap: 2,
                    flexDirection: isMobile ? 'column' : 'row'
                  }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Content Style
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {['concise', 'elaborate'].map((style) => (
                          <Chip
                            key={style}
                            label={style}
                            variant={contentStyle === style ? 'filled' : 'outlined'}
                            onClick={() => handleContentStyle(style)}
                            color="primary"
                            size="small"
                            sx={{ flex: 1 }}
                            disabled={isSpeaking}
                          />
                        ))}
                      </Box>
                    </Box>

                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Duration
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {['small', 'moderate', 'lengthy'].map((length) => (
                          <Chip
                            key={length}
                            label={length}
                            variant={podcastLength === length ? 'filled' : 'outlined'}
                            onClick={() => handleLengthSelection(length)}
                            color="secondary"
                            size="small"
                            sx={{ flex: 1 }}
                            disabled={isSpeaking}
                          />
                        ))}
                      </Box>
                    </Box>
                  </Box>
                </Box>
              )}
            </AnimatedPaper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default App;