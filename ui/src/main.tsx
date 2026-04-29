import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';
import App from './App';
import { DisplayPreferencesProvider } from './DisplayPreferencesProvider';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DisplayPreferencesProvider>
      <App />
    </DisplayPreferencesProvider>
  </StrictMode>
);
