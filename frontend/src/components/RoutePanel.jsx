import React from 'react';

const WIND_DIRS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
const degToDir = (deg) => deg != null ? WIND_DIRS[Math.round(deg / 45) % 8] : '—';

const RoutePanel = ({ brokenCount, minToFly = 3, routeData, droneStatus }) => {
    const isFlying = droneStatus === 'toLamp' || droneStatus === 'return';
    const waiting = !isFlying && brokenCount < minToFly;

    return (
        <div style={{
            position: 'absolute',
            bottom: '20px',
            left: '10px',
            zIndex: 1000,
            background: 'white',
            borderRadius: '12px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
            padding: '10px 14px',
            minWidth: '220px',
            maxWidth: '260px',
            fontFamily: 'sans-serif',
            fontSize: '12px',
            color: '#333',
        }}>
            <div style={{ fontWeight: '600', fontSize: '13px', marginBottom: '6px' }}>
                🤖 Маршрут ИИ
            </div>

            {/* Статус */}
            <div style={{
                fontSize: '11px',
                color: isFlying ? '#2ecc71' : waiting ? '#e67e22' : '#3498db',
                marginBottom: '6px',
                fontWeight: '500',
            }}>
                {isFlying && '✈ Дрон в полёте'}
                {!isFlying && waiting && `⏳ Ожидание: ${brokenCount} / ${minToFly} ламп`}
                {!isFlying && !waiting && brokenCount === 0 && '✓ Сломанных ламп нет'}
                {!isFlying && !waiting && brokenCount >= minToFly && '⚙ Готов к вылету...'}
            </div>

            {/* Данные маршрута */}
            {routeData && !routeData.message && (
                <>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 8px', marginBottom: '8px' }}>
                        <Stat label="Ламп" value={routeData.route_ids?.length ?? 0} />
                        <Stat label="Время" value={`${routeData.flight_time_minutes?.toFixed(1) ?? '—'} мин`} />
                        <Stat label="Батарея" value={`${routeData.battery_usage_percent?.toFixed(1) ?? '—'}%`} />
                        <Stat label="Экономия" value={`${routeData.savings_percent?.toFixed(1) ?? '—'}%`} color="#2ecc71" />
                        <Stat label="Ветер" value={`${routeData.wind_speed?.toFixed(1) ?? '—'} м/с`} />
                        <Stat label="Направление" value={degToDir(routeData.wind_deg)} />
                    </div>
                    <div style={{ fontSize: '11px', color: '#555', marginBottom: '4px' }}>
                        <strong>Порядок:</strong>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {routeData.route_ids?.map((id, i) => (
                            <span key={id} style={{
                                background: '#f0f0f0', borderRadius: '8px',
                                padding: '1px 7px', fontSize: '11px',
                            }}>
                                {i + 1}. #{id}
                            </span>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
};

const Stat = ({ label, value, color }) => (
    <div>
        <div style={{ color: '#999', fontSize: '10px' }}>{label}</div>
        <div style={{ fontWeight: '600', color: color || '#333' }}>{value}</div>
    </div>
);

export default RoutePanel;
