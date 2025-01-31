import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import reactLogo from './assets/react.svg';
import viteLogo from '/vite.svg';
import './App.css';

// Initialize i18n
import i18n from './i18n';

function App() {
  const [count, setCount] = useState(0);
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('en-US');
  const [voices, setVoices] = useState([]);
  const [isSupported, setIsSupported] = useState(true);
  const { t } = useTranslation();

  // Load available voices
  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        const availableVoices = window.speechSynthesis.getVoices();
        setVoices(availableVoices);
      };
      
      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    } else {
      setIsSupported(false);
    }
  }, []);

  const speak = () => {
    if (!isSupported) return;
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language;
    window.speechSynthesis.speak(utterance);
  };

  const changeAppLanguage = (lng) => {
    i18n.changeLanguage(lng);
  };

  return (
    <>
      {/* Existing Counter Section */}
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>{t('welcome')}</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          {t('count')} {count}
        </button>
        <p>
          {t('edit')} <code>src/App.jsx</code> {t('save_to_test')}
        </p>
      </div>

      {/* Text-to-Speech Section */}
      <div className="card">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t('enter_text')}
          rows="3"
          style={{ width: '300px', margin: '10px' }}
        />
        
        {isSupported ? (
          <>
            <select 
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              style={{ margin: '10px' }}
            >
              {voices.map((voice) => (
                <option key={voice.lang} value={voice.lang}>
                  {voice.name} ({voice.lang})
                </option>
              ))}
            </select>
            
            <button onClick={speak} style={{ margin: '10px' }}>
              {t('speak')}
            </button>
          </>
        ) : (
          <p style={{ color: 'red' }}>{t('tts_not_supported')}</p>
        )}
      </div>

      {/* Language Switcher */}
      <div className="card">
        <h3>{t('change_language')}</h3>
        <button onClick={() => changeAppLanguage('en')}>English</button>
        <button onClick={() => changeAppLanguage('es')}>Español</button>
        <button onClick={() => changeAppLanguage('fr')}>Français</button>
      </div>

      <p className="read-the-docs">
        {t('click_logos')}
      </p>
    </>
  );
}

export default App;