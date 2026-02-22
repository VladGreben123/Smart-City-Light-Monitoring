import React, { useEffect, useState } from 'react';

const WeatherCalendar = ({ onTodayWeatherChange }) => {
    const [forecast, setForecast] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isExpanded, setIsExpanded] = useState(false);
    const [override, setOverride] = useState({ enabled: false, is_bad: false });

    const fetchForecast = () => {
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
    };

    const setWeatherMode = async (enabled, is_bad = false) => {
        try {
            await fetch('http://localhost:8000/api/debug/weather-override', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, is_bad }),
            });
            setOverride({ enabled, is_bad });
            fetchForecast();
        } catch (e) {
            console.error('weather-override failed', e);
        }
    };

    useEffect(() => {
        fetchForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [onTodayWeatherChange]);

    if (loading) return null;
    if (error) return <div className="weather-calendar" style={{color: 'red'}}>{error}</div>;

    const today = new Date();
    const currentMonth = today.toLocaleString('ru-RU', { month: 'long' });
    const capitalizedMonth = currentMonth.charAt(0).toUpperCase() + currentMonth.slice(1);

    if (!isExpanded) {
        const todayData = forecast[0] || {};
        const isBad = todayData.is_bad_weather;

        return (
            <div 
                className="weather-calendar collapsed" 
                onClick={() => setIsExpanded(true)}
                style={{ 
                    cursor: 'pointer', 
                    padding: '16px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '16px',
                    background: '#2b2d30', // Yandex-like dark panel
                    borderRadius: '16px',
                    boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
                    color: '#f2f2f2',
                    border: '1px solid #3c3f41' // Subtle border
                }}
            >
                {/* Header Status */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px', // Slightly more squared for Yandex feel
                        background: isBad ? 'rgba(255, 92, 92, 0.15)' : 'rgba(90, 196, 94, 0.15)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '24px',
                        border: isBad ? '1px solid rgba(255, 92, 92, 0.3)' : '1px solid rgba(90, 196, 94, 0.3)'
                    }}>
                        {isBad ? '⛔' : '✈️'}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <span style={{ 
                            fontSize: '12px', 
                            textTransform: 'uppercase', 
                            color: '#8f9298',
                            fontWeight: '600',
                            letterSpacing: '0.5px'
                        }}>
                            Сегодня, {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
                        </span>
                        <span style={{ 
                            fontSize: '17px', 
                            fontWeight: '700',
                            color: isBad ? '#ff5c5c' : '#5ac45e' // Brighter/Neon
                        }}>
                            {isBad ? 'Полеты запрещены' : 'Полеты разрешены'}
                        </span>
                    </div>
                    <div style={{ marginLeft: 'auto', color: '#8f9298' }}>
                        ▼
                    </div>
                </div>

                {/* Mini Week Strip */}
                <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between',
                    borderTop: '1px solid #3c3f41',
                    paddingTop: '14px'
                }}>
                    {forecast.slice(0, 7).map((day, index) => {
                         const date = new Date(day.date);
                         const dayName = date.toLocaleDateString('ru-RU', { weekday: 'short' });
                         const isToday = index === 0;

                         return (
                            <div
                                key={day.date}
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}
                            >
                                <span style={{ 
                                    fontSize: '11px', 
                                    color: isToday ? '#fff' : '#8f9298',
                                    fontWeight: isToday ? '700' : '500'
                                }}>
                                    {dayName}
                                </span>
                                <div style={{
                                    width: '10px',
                                    height: '10px',
                                    borderRadius: '50%',
                                    backgroundColor: day.is_bad_weather ? '#ff5c5c' : '#5ac45e',
                                    boxShadow: isToday ? '0 0 0 2px #2b2d30, 0 0 0 4px #5c9ce6' : 'none' // Blue active ring
                                }}></div>
                            </div>
                         );
                    })}
                </div>
            </div>
        );
    }

    return (
        <div className="weather-calendar expanded" style={{ 
            minWidth: '460px', 
            background: '#2b2d30',
            borderRadius: '16px',
            boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
            padding: '24px',
            maxHeight: '80vh',
            overflowY: 'auto',
            color: '#f2f2f2',
            border: '1px solid #3c3f41'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h3 style={{ margin: 0, fontSize: '22px', fontWeight: '700', color: '#fff' }}>Прогноз полетов</h3>
                <button 
                    onClick={(e) => { e.stopPropagation(); setIsExpanded(false); }}
                    style={{ 
                        background: '#3c3f41', 
                        border: 'none', 
                        cursor: 'pointer', 
                        fontSize: '20px',
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#f2f2f2',
                        transition: 'background 0.2s'
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = '#4b4e52'}
                    onMouseOut={(e) => e.currentTarget.style.background = '#3c3f41'}
                >
                    ✕
                </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {forecast.map((day, index) => {
                    const date = new Date(day.date);
                    const dayName = date.toLocaleDateString('ru-RU', { weekday: 'long' });
                    const dateStr = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
                    const isToday = index === 0;

                    return (
                        <div
                            key={day.date}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                padding: '16px',
                                borderRadius: '12px',
                                backgroundColor: day.is_bad_weather ? 'rgba(255, 92, 92, 0.08)' : 'rgba(90, 196, 94, 0.08)',
                                border: isToday ? '2px solid #5c9ce6' : '1px solid transparent', // Blue active border
                                gap: '20px'
                            }}
                        >
                            <div style={{ 
                                fontSize: '28px',
                                width: '48px',
                                height: '48px',
                                borderRadius: '10px',
                                background: day.is_bad_weather ? 'rgba(255, 92, 92, 0.15)' : 'rgba(90, 196, 94, 0.15)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                            }}>
                                {day.is_bad_weather ? '⛔' : '✈️'}
                            </div>
                            
                            <div style={{ flex: 1 }}>
                                <div style={{ 
                                    fontSize: '17px', 
                                    fontWeight: '600', 
                                    color: '#fff',
                                    textTransform: 'capitalize' 
                                }}>
                                    {isToday ? 'Сегодня' : dayName}
                                </div>
                                <div style={{ fontSize: '13px', color: '#8f9298', marginTop: '2px' }}>
                                    {dateStr}
                                </div>
                            </div>

                            <div style={{ textAlign: 'right' }}>
                                <div style={{ 
                                    fontSize: '18px', 
                                    fontWeight: '700',
                                    color: day.is_bad_weather ? '#ff5c5c' : '#5ac45e' 
                                }}>
                                    {Math.round(day.temp_min)}°C
                                </div>
                                {day.is_bad_weather && (
                                    <div style={{ fontSize: '12px', color: '#ff5c5c', fontWeight: '500', marginTop: '2px' }}>
                                        {day.reason || 'Непогода'}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div style={{ marginTop: '24px', borderTop: '1px solid #3c3f41', paddingTop: '20px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#8f9298', marginBottom: '14px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Симуляция погоды (Debug)
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button onClick={() => setWeatherMode(true, false)} style={{
                        flex: 1,
                        padding: '12px', 
                        fontSize: '13px', 
                        borderRadius: '10px', 
                        border: 'none',
                        background: override.enabled && !override.is_bad ? '#5ac45e' : '#3c3f41',
                        color: override.enabled && !override.is_bad ? '#1e1e1e' : '#f2f2f2', 
                        cursor: 'pointer',
                        fontWeight: '600',
                        transition: 'all 0.2s'
                    }}>☀️ Хорошая</button>
                    <button onClick={() => setWeatherMode(true, true)} style={{
                        flex: 1,
                        padding: '12px', 
                        fontSize: '13px', 
                        borderRadius: '10px', 
                        border: 'none',
                        background: override.enabled && override.is_bad ? '#ff5c5c' : '#3c3f41',
                        color: override.enabled && override.is_bad ? '#1e1e1e' : '#f2f2f2', 
                        cursor: 'pointer',
                        fontWeight: '600',
                        transition: 'all 0.2s'
                    }}>⛈️ Плохая</button>
                    <button onClick={() => setWeatherMode(false)} style={{
                        flex: 1,
                        padding: '12px', 
                        fontSize: '13px', 
                        borderRadius: '10px', 
                        border: 'none',
                        background: !override.enabled ? '#5c9ce6' : '#3c3f41',
                        color: !override.enabled ? '#1e1e1e' : '#f2f2f2', 
                        cursor: 'pointer',
                        fontWeight: '600',
                        transition: 'all 0.2s'
                    }}>📡 Реальная</button>
                </div>
            </div>
        </div>
    );
};

export default WeatherCalendar;
