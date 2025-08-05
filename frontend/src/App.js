import React, { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Компонент статистики
const DashboardStats = ({ stats, onRefresh }) => {
  if (!stats) return <div className="text-center">Загрузка статистики...</div>;

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">📊 Статистика системы</h2>
        <button 
          onClick={onRefresh}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
        >
          🔄 Обновить
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4 rounded-lg">
          <div className="text-3xl font-bold">{stats.totals?.trends || 0}</div>
          <div className="text-blue-100">Собрано трендов</div>
        </div>
        <div className="bg-gradient-to-r from-green-500 to-green-600 text-white p-4 rounded-lg">
          <div className="text-3xl font-bold">{stats.totals?.content || 0}</div>
          <div className="text-green-100">Создано контента</div>
        </div>
        <div className="bg-gradient-to-r from-purple-500 to-purple-600 text-white p-4 rounded-lg">
          <div className="text-3xl font-bold">{stats.totals?.publications || 0}</div>
          <div className="text-purple-100">Публикаций</div>
        </div>
      </div>

      {stats.platform_stats && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3">📱 По платформам:</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(stats.platform_stats).map(([platform, count]) => (
              <div key={platform} className="bg-gray-50 p-3 rounded-lg text-center">
                <div className="font-semibold text-lg">{count}</div>
                <div className="text-sm text-gray-600 capitalize">{platform}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats.recent_trends && stats.recent_trends.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">🔥 Последние тренды:</h3>
          <div className="space-y-2">
            {stats.recent_trends.slice(0, 3).map((trend, idx) => (
              <div key={idx} className="bg-gray-50 p-3 rounded-lg">
                <div className="font-medium text-sm">{trend.title}</div>
                <div className="text-xs text-gray-500">
                  {trend.source} • Score: {trend.popularity_score}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Компонент управления трендами
const TrendsManager = ({ onTrendsUpdate, onSelectedTrendsUpdate }) => {
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTrends, setSelectedTrends] = useState([]);

  const collectTrends = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/trends`);
      setTrends(response.data.trends);
      onTrendsUpdate(response.data.trends);
    } catch (error) {
      console.error("Ошибка сбора трендов:", error);
      alert("Ошибка при сборе трендов");
    } finally {
      setLoading(false);
    }
  };

  const toggleTrendSelection = (trendId) => {
    const newSelectedTrends = selectedTrends.includes(trendId) 
      ? selectedTrends.filter(id => id !== trendId)
      : [...selectedTrends, trendId];
    
    setSelectedTrends(newSelectedTrends);
    onSelectedTrendsUpdate(newSelectedTrends);
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">🔍 Управление трендами</h2>
        <button 
          onClick={collectTrends}
          disabled={loading}
          className="bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white px-6 py-2 rounded-lg transition-colors"
        >
          {loading ? "⏳ Собираем..." : "🔍 Собрать тренды"}
        </button>
      </div>

      {trends.length > 0 && (
        <>
          <div className="mb-4 text-sm text-gray-600">
            Найдено трендов: {trends.length} | Выбрано: {selectedTrends.length}
          </div>
          
          <div className="max-h-96 overflow-y-auto space-y-3">
            {trends.map((trend, idx) => (
              <div 
                key={trend.id}
                className={`border-2 p-4 rounded-lg cursor-pointer transition-colors ${
                  selectedTrends.includes(trend.id) 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => toggleTrendSelection(trend.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-800 mb-1">{trend.title}</h3>
                    <div className="text-sm text-gray-600 mb-2">
                      {trend.source} • Score: {trend.popularity_score}
                    </div>
                    {trend.keywords && trend.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {trend.keywords.slice(0, 3).map((keyword, kidx) => (
                          <span key={kidx} className="bg-gray-100 text-xs px-2 py-1 rounded">
                            {keyword}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                    selectedTrends.includes(trend.id)
                      ? 'bg-blue-500 border-blue-500'
                      : 'border-gray-300'
                  }`}>
                    {selectedTrends.includes(trend.id) && (
                      <span className="text-white text-sm">✓</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

// Компонент генерации контента
const ContentGenerator = ({ selectedTrends, onContentGenerated }) => {
  const [platforms] = useState(["telegram", "youtube_shorts", "tiktok"]);
  const [selectedPlatforms, setSelectedPlatforms] = useState(["telegram"]);
  const [generating, setGenerating] = useState(false);
  const [content, setContent] = useState(null);
  const [generateVideos, setGenerateVideos] = useState(false);
  const [withVoice, setWithVoice] = useState(true);
  const [monetize, setMonetize] = useState(true);

  const generateContent = async () => {
    if (selectedTrends.length === 0) {
      alert("Выберите хотя бы один тренд");
      return;
    }

    setGenerating(true);
    try {
      const response = await axios.post(`${API}/content/generate`, {
        trend_ids: selectedTrends,
        platforms: selectedPlatforms
      });
      setContent(response.data.content);
    } catch (error) {
      console.error("Ошибка генерации контента:", error);
      alert("Ошибка при генерации контента");
    } finally {
      setGenerating(false);
    }
  };

  const publishToTelegram = async () => {
    if (!content || !content.telegram) {
      alert("Нет контента для публикации");
      return;
    }

    try {
      const contentIds = content.telegram.map(item => item.id);
      const response = await axios.post(`${API}/publish/telegram`, {
        content_ids: contentIds,
        channel_key: "main",
        delay_seconds: 10
      });
      alert(`✅ ${response.data.message}`);
    } catch (error) {
      console.error("Ошибка публикации:", error);
      alert("Ошибка при публикации в Telegram");
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">🤖 Генерация контента</h2>
      
      <div className="mb-6">
        <h3 className="font-semibold mb-3">📱 Выберите платформы:</h3>
        <div className="flex flex-wrap gap-3">
          {platforms.map(platform => (
            <label key={platform} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={selectedPlatforms.includes(platform)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedPlatforms([...selectedPlatforms, platform]);
                  } else {
                    setSelectedPlatforms(selectedPlatforms.filter(p => p !== platform));
                  }
                }}
                className="rounded"
              />
              <span className="capitalize">{platform.replace('_', ' ')}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="flex gap-4 mb-6">
        <button
          onClick={generateContent}
          disabled={generating || selectedTrends.length === 0}
          className="bg-purple-500 hover:bg-purple-600 disabled:bg-gray-400 text-white px-6 py-2 rounded-lg transition-colors"
        >
          {generating ? "⏳ Генерируем..." : "🎯 Создать контент"}
        </button>
        
        {content && content.telegram && (
          <button
            onClick={publishToTelegram}
            className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
          >
            📤 Опубликовать в Telegram
          </button>
        )}
      </div>

      {content && (
        <div className="space-y-4">
          <h3 className="font-semibold text-lg">📝 Созданный контент:</h3>
          {Object.entries(content).map(([platform, items]) => (
            <div key={platform} className="border rounded-lg p-4">
              <h4 className="font-medium mb-3 capitalize">
                {platform.replace('_', ' ')} ({items.length} постов)
              </h4>
              <div className="space-y-3">
                {items.map((item, idx) => (
                  <div key={idx} className="bg-gray-50 p-3 rounded">
                    <div className="font-medium text-sm mb-2">{item.title}</div>
                    <div className="text-sm text-gray-700 mb-2">
                      {item.content.substring(0, 150)}...
                    </div>
                    {item.hashtags && (
                      <div className="flex flex-wrap gap-1">
                        {item.hashtags.slice(0, 5).map((tag, tidx) => (
                          <span key={tidx} className="bg-blue-100 text-xs px-2 py-1 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Главное приложение
function App() {
  const [stats, setStats] = useState(null);
  const [trends, setTrends] = useState([]);
  const [selectedTrends, setSelectedTrends] = useState([]);
  const [systemStatus, setSystemStatus] = useState(null);

  const loadDashboardStats = async () => {
    try {
      const response = await axios.get(`${API}/stats/dashboard`);
      setStats(response.data);
    } catch (error) {
      console.error("Ошибка загрузки статистики:", error);
    }
  };

  const loadSystemStatus = async () => {
    try {
      const response = await axios.get(`${API}/status`);
      setSystemStatus(response.data);
    } catch (error) {
      console.error("Ошибка загрузки статуса:", error);
    }
  };

  const runFullAutomation = async () => {
    try {
      const response = await axios.get(`${API}/automation/run`);
      alert(`🚀 ${response.data.message}\n\nЭтапы: ${response.data.steps.join(' → ')}\n\nВремя выполнения: ${response.data.estimated_time}`);
      // Обновляем статистику через некоторое время
      setTimeout(loadDashboardStats, 10000); // Обновляем через 10 секунд
    } catch (error) {
      console.error("Ошибка запуска автоматизации:", error);
      alert("Ошибка запуска автоматизации");
    }
  };

  useEffect(() => {
    loadDashboardStats();
    loadSystemStatus();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100">
      <div className="container mx-auto px-4 py-8">
        {/* Заголовок */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-4">
            🚀 EKOSYSTEMA_FULL
          </h1>
          <p className="text-xl text-gray-600 mb-6">
            Автоматическая система создания и публикации контента
          </p>
          
          <div className="flex justify-center space-x-4">
            <button
              onClick={runFullAutomation}
              className="bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white px-8 py-3 rounded-xl font-semibold shadow-lg transition-all"
            >
              ⚡ Запустить автоматизацию
            </button>
            
            <button
              onClick={loadDashboardStats}
              className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-8 py-3 rounded-xl font-semibold shadow-lg transition-all"
            >
              🔄 Обновить данные
            </button>
          </div>
        </div>

        {/* Статус системы */}
        {systemStatus && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">⚙️ Статус системы</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(systemStatus.services).map(([service, status]) => (
                <div key={service} className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${status === 'active' ? 'bg-green-500' : 'bg-red-500'}`}></div>
                  <span className="font-medium capitalize">{service.replace('_', ' ')}</span>
                  <span className={`text-sm px-2 py-1 rounded ${status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Статистика */}
        <DashboardStats stats={stats} onRefresh={loadDashboardStats} />

        {/* Управление трендами */}
        <TrendsManager 
          onTrendsUpdate={(newTrends) => setTrends(newTrends)} 
          onSelectedTrendsUpdate={(selected) => setSelectedTrends(selected)}
        />

        {/* Генерация контента */}
        <ContentGenerator 
          selectedTrends={selectedTrends}
          onContentGenerated={(newContent) => {
            console.log("Контент сгенерирован:", newContent);
            // Здесь можно добавить логику обработки нового контента
          }}
        />

        {/* Футер */}
        <div className="text-center text-gray-500 mt-12">
          <p>EKOSYSTEMA_FULL v1.0.0 | Автоматизация контент-маркетинга</p>
        </div>
      </div>
    </div>
  );
}

export default App;