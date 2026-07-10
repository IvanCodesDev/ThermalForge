import React, { useState } from 'react';
import { LayoutDashboard, MessageSquare, ShieldCheck, ChevronDown, Hexagon } from 'lucide-react';
import Dashboard from './components/Dashboard';
import AIChat from './components/AIChat';
import SafetyOps from './components/SafetyOps';

enum Tab {
  HOME = 'home',
  AI_CHAT = 'ai_chat',
  SAFETY = 'safety'
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>(Tab.HOME);

  const renderContent = () => {
    switch (activeTab) {
      case Tab.HOME:
        return <Dashboard />;
      case Tab.AI_CHAT:
        return <AIChat />;
      case Tab.SAFETY:
        return <SafetyOps />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-[#050505] text-white font-sans overflow-hidden p-5 flex-col">
      {/* Top Navigation Bar - CoinUnity Style */}
      <header className="flex justify-between items-center mb-6 shrink-0 z-50">

        {/* Logo */}
        <div className="flex items-center gap-2 text-xl font-bold">
          <Hexagon className="text-brand-500 fill-brand-500/20" size={24} strokeWidth={2.5} />
          <span>视锂工坊</span>
        </div>

        {/* Navigation Tabs - Pill Shape Container */}
        <nav className="flex gap-1 bg-[#121212] border border-white/10 p-1.5 rounded-full">
          <button
            onClick={() => setActiveTab(Tab.HOME)}
            className={`px-6 py-1.5 rounded-full text-sm font-medium transition-all duration-300 ${activeTab === Tab.HOME
                ? 'bg-brand-600 text-white shadow-[0_0_10px_rgba(249,115,22,0.3)]'
                : 'text-[#888888] hover:text-white hover:bg-white/5'
              }`}
          >
            平台首页
          </button>
          <button
            onClick={() => setActiveTab(Tab.AI_CHAT)}
            className={`px-6 py-1.5 rounded-full text-sm font-medium transition-all duration-300 ${activeTab === Tab.AI_CHAT
                ? 'bg-brand-600 text-white shadow-[0_0_10px_rgba(249,115,22,0.3)]'
                : 'text-[#888888] hover:text-white hover:bg-white/5'
              }`}
          >
            智能问答
          </button>
          <button
            onClick={() => setActiveTab(Tab.SAFETY)}
            className={`px-6 py-1.5 rounded-full text-sm font-medium transition-all duration-300 ${activeTab === Tab.SAFETY
                ? 'bg-brand-600 text-white shadow-[0_0_10px_rgba(249,115,22,0.3)]'
                : 'text-[#888888] hover:text-white hover:bg-white/5'
              }`}
          >
            安全与运维
          </button>
        </nav>

        {/* User Profile - Pill Shape */}
        <div className="flex items-center gap-3 bg-[#121212] border border-white/10 px-4 py-1.5 rounded-full cursor-pointer hover:border-white/20 transition-colors">
          <img
            src="https://ui-avatars.com/api/?name=Admin+User&background=333&color=fff"
            className="w-6 h-6 rounded-full"
            alt="User"
          />
          <div className="flex flex-col leading-none">
            <span className="text-xs font-bold text-white">管理员</span>
            <span className="text-[10px] text-[#666]">#sys-001</span>
          </div>
          <ChevronDown size={14} className="text-[#666]" />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full relative overflow-hidden rounded-[20px] bg-transparent">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;