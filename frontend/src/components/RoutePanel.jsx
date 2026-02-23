import React from 'react';

const WIND_DIRS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
const degToDir = (deg) => deg != null ? WIND_DIRS[Math.round(deg / 45) % 8] : '—';

const RoutePanel = ({ brokenCount, minToFly = 3, routeData, droneStatus }) => {
    const isFlying = droneStatus === 'toLamp' || droneStatus === 'return';
    const waiting = !isFlying && brokenCount < minToFly;

    return (
        <div
            className="glass-panel"
            style={{
                padding: '12px 16px',
                minWidth: '240px',
                maxWidth: '300px',
                fontFamily: 'sans-serif',
                fontSize: '12px',
                color: '#f2f2f2'
            }}
        >
            <div style={{ fontWeight: '600', fontSize: '13px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: isFlying ? '#5ac45e' : waiting ? '#ffb74d' : '#5c9ce6',
                        boxShadow: isFlying
                            ? '0 0 8px rgba(90,196,94,0.5)'
                            : waiting
                                ? '0 0 8px rgba(255,183,77,0.5)'
                                : '0 0 8px rgba(92,156,230,0.5)'
                    }} />
                    <span>Маршрут дрона</span>
                </span>
                {routeData?.timestamp && !isFlying && (
                    <span style={{ fontSize: '10px', color: '#8f9298', fontWeight: 'normal' }}>
                        {new Date(routeData.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                )}
            </div>

            {/* Статус */}
            <div style={{
                fontSize: '11px',
                color: isFlying ? '#2ecc71' : waiting ? '#e67e22' : '#3498db',
                marginBottom: '8px',
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
                    <div style={{ fontSize: '11px', color: '#8f9298', marginBottom: '4px' }}>
                        <strong>Порядок:</strong>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {routeData.route_ids?.map((id, i) => (
                            <span key={id} style={{
                                background: '#3c3f41',
                                borderRadius: '8px',
                                padding: '2px 8px',
                                fontSize: '11px',
                                color: '#f2f2f2',
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
        <div style={{ color: '#8f9298', fontSize: '10px' }}>{label}</div>
        <div style={{ fontWeight: '600', color: color || '#f2f2f2' }}>{value}</div>
    </div>
);

export default RoutePanel;
