import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import BlackhorsePipeline from './BlackhorsePipeline.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BlackhorsePipeline />
  </StrictMode>,
)
