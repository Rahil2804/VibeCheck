import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/newsreader/latin-500.css';
import '@fontsource/newsreader/latin-700.css';
import './styles.css';

createRoot(document.getElementById('root')).render(<App />);
