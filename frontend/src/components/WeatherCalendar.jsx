import React, { useEffect, useState } from 'react';

const WeatherCalendar = ({ onTodayWeatherChange }) => {
    const [forecast, setForecast] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        // Запрос к бэкенду
        fetch('http://localhost:8000/api/weather/forecast')
            .then(res => {
                if (!res.ok) throw new Error('Network response was not ok');
                return res.json();
            })
            .then(data => {
                if (!Array.isArray(data)) {
                    console.error('API returned non-array:', data);
                    throw new Error('Invalid data format');
                }
                setForecast(data);
                setLoading(false);
                
                // Найти сегодняшнюю дату и передать статус
                const today = new Date();
                const year = today.getFullYear();
                const month = String(today.getMonth() + 1).padStart(2, '0');
                const day = String(today.getDate()).padStart(2, '0');
                const todayStr = `${year}-${month}-${day}`;
                
                const todayData = data.find(d => d.date === todayStr);
                if (todayData && onTodayWeatherChange) {
                    onTodayWeatherChange(todayData.is_bad_weather);
                } else if (onTodayWeatherChange) {
                    onTodayWeatherChange(false); // Default to good if no data
                }
            })
            .catch(err => {
                console.error('Failed to fetch weather:', err);
                setError('Ошибка загрузки погоды');
                setLoading(false);
            });
    }, [onTodayWeatherChange]);

    if (loading) return null;
    if (error) return <div className="weather-calendar" style={{color: 'red'}}>{error}</div>;

    return (
        <div className="weather-calendar">
            <h3>Погодный календарь</h3>
            <div className="calendar-grid">
                {forecast.map(day => (
                    <div 
                        key={day.date} 
                        className={`calendar-day ${day.is_bad_weather ? 'bad' : 'good'}`}
                        title={day.reason}
                    >
                        <span className="date">
                            {(() => {
                                const [y, m, d] = day.date.split('-');
                                const date = new Date(y, m - 1, d);
                                return date.toLocaleDateString('ru-RU', {day: 'numeric', month: 'short'});
                            })()}
                        </span>
                        <span className="temp">{Math.round(day.temp_min)}°C</span>
                        <span className="icon">
                            {day.is_bad_weather ? '⛔' : '✈️'}
                        </span>
                    </div>
                ))}
            </div>
            <div style={{fontSize: '10px', marginTop: '5px', textAlign: 'center', color: '#888'}}>
                ⛔ - Полеты запрещены<br/>
                ✈️ - Полеты разрешены
            </div>
        </div>
    );
};

export default WeatherCalendar;
