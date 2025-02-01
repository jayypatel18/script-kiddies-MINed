import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
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
  VolumeUp,
  Download
} from '@mui/icons-material';
import { styled, alpha, keyframes } from '@mui/material/styles';

const ELEVEN_LABS_CONFIG = {
  apiKey: import.meta.env.VITE_ELEVEN_LABS_API_KEY,
  voiceId: import.meta.env.VITE_ELEVEN_LABS_VOICE_ID || '21m00Tcm4TlvDq8ikWAM',
  model: 'eleven_monolingual_v1',
  stability: 0.5,
  similarityBoost: 0.75
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
  transition: 'background-color 0.3s ease'
}));

const GradientAppBar = styled(AppBar)(({ theme }) => ({
  background: `linear-gradient(45deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 100%)`,
  boxShadow: 'none'
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
  backgroundColor:
    isdragactive === 'true' ? alpha(theme.palette.primary.light, 0.1) : theme.palette.background.paper,
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
  const [loading, setLoading] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [currentSentence, setCurrentSentence] = useState(-1);
  const [isPaused, setIsPaused] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [podcastLength, setPodcastLength] = useState(null);
  const [contentStyle, setContentStyle] = useState(null);
  const [validationError, setValidationError] = useState('');
  const [generatingDownload, setGeneratingDownload] = useState(false);

  const audioRef = useRef(null);
  const currentIndexRef = useRef(-1);

  const sentences = useMemo(
    () => output.match(/[^.!?]+[.!?]|[^.!?]+$/g) || [],
    [output]
  );

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }
    };
  }, []);

  const handleDownload = async () => {
    if (!output) return;
    
    try {
      setGeneratingDownload(true);
      const response = await axios.post(
        `https://api.elevenlabs.io/v1/text-to-speech/${ELEVEN_LABS_CONFIG.voiceId}`,
        {
          text: output,
          model_id: ELEVEN_LABS_CONFIG.model,
          voice_settings: {
            stability: ELEVEN_LABS_CONFIG.stability,
            similarity_boost: ELEVEN_LABS_CONFIG.similarityBoost
          }
        },
        {
          responseType: 'blob',
          headers: {
            'xi-api-key': ELEVEN_LABS_CONFIG.apiKey,
            'Content-Type': 'application/json'
          }
        }
      );

      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'podcast.mp3';
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(link);
    } catch (error) {
      console.error('Download error:', error);
      setSpeechError('Error generating download');
    } finally {
      setGeneratingDownload(false);
    }
  };

  const playSentence = async (index) => {
    if (index >= sentences.length) {
      setIsSpeaking(false);
      return;
    }

    setCurrentSentence(index);
    const sentence = sentences[index].trim();
    if (!sentence) {
      await playSentence(index + 1);
      return;
    }

    try {
      const response = await axios.post(
        `https://api.elevenlabs.io/v1/text-to-speech/${ELEVEN_LABS_CONFIG.voiceId}`,
        {
          text: sentence,
          model_id: ELEVEN_LABS_CONFIG.model,
          voice_settings: {
            stability: ELEVEN_LABS_CONFIG.stability,
            similarity_boost: ELEVEN_LABS_CONFIG.similarityBoost
          }
        },
        {
          responseType: 'blob',
          headers: {
            'xi-api-key': ELEVEN_LABS_CONFIG.apiKey,
            'Content-Type': 'application/json'
          }
        }
      );

      const audioUrl = URL.createObjectURL(response.data);
      const newAudio = new Audio(audioUrl);
      audioRef.current = newAudio;

      newAudio.addEventListener('ended', () => {
        URL.revokeObjectURL(audioUrl);
        playSentence(index + 1);
      });

      newAudio.addEventListener('pause', () => {
        setIsPaused(true);
      });

      newAudio.addEventListener('play', () => {
        setIsPaused(false);
      });

      await newAudio.play();
    } catch (err) {
      console.error('Audio error:', err);
      setSpeechError('Error playing audio');
      setIsSpeaking(false);
    }
  };

  const speakText = async (text) => {
    if (!text) return;
    setIsSpeaking(true);
    setIsPaused(false);
    setCurrentSentence(-1);

    try {
      await playSentence(0);
    } catch (error) {
      console.error('Speech error:', error);
      setSpeechError('Error generating speech');
      setIsSpeaking(false);
    }
  };

  const validateSelections = () => {
    if (!podcastLength || !contentStyle || files.length === 0) {
      setValidationError('Please select PDFs, duration, and content style before generating');
      return false;
    }
    setValidationError('');
    return true;
  };

  const handlePlayPause = () => {
    if (isSpeaking) {
      if (isPaused) {
        audioRef.current?.play();
      } else {
        audioRef.current?.pause();
      }
    } else {
      speakText(output);
    }
  };

  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }
    setIsSpeaking(false);
    setIsPaused(false);
    setCurrentSentence(-1);
  };

  const onDrop = useCallback((acceptedFiles) => {
    const pdfFiles = acceptedFiles.filter((file) => file.type === 'application/pdf');
    setFiles((prev) => [
      ...prev,
      ...pdfFiles.map((file) => Object.assign(file, { preview: URL.createObjectURL(file) }))
    ]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true
  });

  const handleSubmit = async () => {
    if (!validateSelections()) return;
    try {
      setLoading(true);
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('pdfs', file);
      });
      formData.append('contentStyle', contentStyle);
      formData.append('duration', podcastLength);

      const response = await fetch('/api/generate', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('API request failed');

      const data = await response.json();
      setOutput(data.summary);
    } catch (error) {
      console.error(error);
      setOutput('Error generating podcast script');
    } finally {
      setLoading(false);
    }
  };

  const removeFile = (fileName) => {
    setFiles(files.filter((file) => file.name !== fileName));
  };

  const hasContent = output.length > 0;

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', width: '100vw' }}>
      <GradientAppBar position="sticky">
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <VolumeUp sx={{ mr: 2, fontSize: 32, color: 'white' }} />
            <Box>
              <Typography variant="h6" fontWeight="700" color="white">
                VoiceCraft Studio
              </Typography>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                Transform research papers into podcasts
              </Typography>
            </Box>
          </Box>
        </Toolbar>
      </GradientAppBar>

      <Container
        maxWidth="lg"
        sx={{
          py: 4,
          display: 'flex',
          justifyContent: 'center',
          [theme.breakpoints.up('md')]: {
            maxWidth: '90%'
          }
        }}
      >
        <Grid container spacing={4} sx={{ width: '100%', alignItems: 'stretch' }}>
          <Grid
            item
            xs={12}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              [theme.breakpoints.up('md')]: {
                flexBasis: '40%',
                maxWidth: '50%',
                height: '100%'
              }
            }}
          >
            <AnimatedPaper elevation={3} sx={{ p: 3, flex: 1 }}>
              <Typography variant="subtitle1" fontWeight="600" mb={2}>
                Input Settings
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
                    Drag &amp; drop PDF files
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    (Multiple files supported)
                  </Typography>
                </Box>
              </StyledDropzone>

              {files.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="caption"
                    fontWeight="500"
                    color="text.secondary"
                  >
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
                          pr: 8,
                          position: 'relative'
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

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="caption"
                  fontWeight="500"
                  color="text.secondary"
                  display="block"
                  mb={1}
                >
                  Content Style
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {[
                    'concise',
                    'elaborate',
                    'balanced',
                    'formal',
                    'casual',
                    'professional'
                  ].map((style) => (
                    <Chip
                      key={style}
                      label={style}
                      variant={contentStyle === style ? 'filled' : 'outlined'}
                      onClick={() => setContentStyle(style)}
                      color="primary"
                      size="small"
                      sx={{ textTransform: 'capitalize' }}
                    />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="caption"
                  fontWeight="500"
                  color="text.secondary"
                  display="block"
                  mb={1}
                >
                  Podcast Duration
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {['small', 'moderate', 'lengthy'].map((length) => (
                    <Chip
                      key={length}
                      label={length}
                      variant={podcastLength === length ? 'filled' : 'outlined'}
                      onClick={() => setPodcastLength(length)}
                      color="secondary"
                      size="small"
                      sx={{ textTransform: 'capitalize' }}
                    />
                  ))}
                </Box>
              </Box>

              {validationError && (
                <Typography color="error" variant="caption" display="block" mb={2}>
                  {validationError}
                </Typography>
              )}

              <Button
                fullWidth
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || files.length === 0}
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

          <Grid
            item
            xs={12}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              [theme.breakpoints.up('md')]: {
                flexBasis: '60%',
                maxWidth: '50%',
                height: '100%'
              }
            }}
          >
            <AnimatedPaper elevation={3} sx={{ p: 3, flex: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="subtitle1" fontWeight="600" mb={2}>
                  Podcast Preview
                </Typography>
                {hasContent && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <VoiceActivityIndicator active={isSpeaking && !isPaused} />
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
                        bgcolor:
                          index === currentSentence
                            ? alpha(theme.palette.primary.light, 0.3)
                            : 'transparent',
                        transition: 'background-color 0.3s ease'
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: index === currentSentence ? 600 : 400,
                          color:
                            index === currentSentence
                              ? alpha(theme.palette.primary.dark, 0.8)
                              : 'text.primary'
                        }}
                      >
                        {sentence}
                      </Typography>
                    </Box>
                  ))
                ) : (
                  <Box
                    sx={{
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'text.secondary'
                    }}
                  >
                    <Typography variant="body2">
                      Generated script will appear here
                    </Typography>
                  </Box>
                )}
              </Paper>

              {hasContent && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    flexDirection: isMobile ? 'column' : 'row'
                  }}
                >
                  <PlayButton
                    variant="contained"
                    onClick={handlePlayPause}
                    disabled={!isSpeaking && sentences.length === 0}
                    startIcon={isSpeaking && !isPaused ? <Pause /> : <PlayArrow />}
                  >
                    {!isSpeaking ? 'Play' : isPaused ? 'Resume' : 'Pause'}
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

                  <Button
                    variant="contained"
                    color="secondary"
                    onClick={handleDownload}
                    disabled={generatingDownload || !hasContent}
                    startIcon={<Download />}
                    sx={{
                      borderRadius: '28px',
                      textTransform: 'none',
                      width: isMobile ? '100%' : 'auto'
                    }}
                  >
                    {generatingDownload ? 'Generating...' : 'Download MP3'}
                  </Button>
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