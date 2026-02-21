import { useState, useEffect } from 'react'

function App() {
  const [message, setMessage] = useState('Загрузка...')

  useEffect(() => {
    fetch('http://127.0.0.1:8000/')
      .then(res => res.json())
      .then(data => setMessage(data.message))
      .catch(err => setMessage('Ошибка соединения'))
  }, [])

  return (
    <div style={{ textAlign: 'center', marginTop: '50px' }}>
      <h1>React + FastAPI</h1>
      <p>Ответ от сервера: {message}</p>
    </div>
  )
}

export default App