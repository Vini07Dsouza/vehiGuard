import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource-variable/unbounded'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './auth.jsx'
import CustomCursor from './components/CustomCursor.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <CustomCursor />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
