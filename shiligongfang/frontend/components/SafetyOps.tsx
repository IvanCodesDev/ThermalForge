import React from 'react';
import { Shield, Radio, Lock, Activity, Server, AlertOctagon, RefreshCw, FileText, CheckCircle2 } from 'lucide-react';
import { LogEntry } from '../types';

const mockLogs: LogEntry[] = [
  { id: '1', timestamp: '14:32:01', level: 'info', message: 'PLC_Block_01 连接建立成功', source: 'Network' },
  { id: '2', timestamp: '14:31:45', level: 'warning', message: '机械臂关节 J2 温度稍高 (65°C)', source: 'PLC' },
  { id: '3', timestamp: '14:30:12', level: 'info', message: 'AI 视觉模型热更新完成', source: 'AI', operator: 'System' },
  { id: '4', timestamp: '14:28:00', level: 'critical', message: '检测到非授权区域人员闯入', source: 'System', operator: 'Sensor #4' },
  { id: '5', timestamp: '14:15:22', level: 'info', message: '常规巡检任务生成', source: 'System' },
];

const SafetyOps: React.FC = () => {
  return (
    <div className="h-full overflow-y-auto pr-2 relative [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">

      {/* Top Row: Mode & Safety */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">

        {/* Run Mode */}
        <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden flex flex-col justify-between shadow-lg min-h-[180px]">
          <div className="glow-bg"></div>
          <div className="flex justify-between items-start z-10">
            <div>
              <h3 className="text-sm text-dark-text">运行模式</h3>
              <div className="mt-2 text-2xl font-bold text-[#00ff88] flex items-center gap-2">
                <RefreshCw className="animate-spin-slow" size={20} />
                全自动运行
              </div>
              <p className="text-xs text-gray-500 mt-2">当前节拍目标：4.5s</p>
            </div>
            <div className="bg-[#00ff88]/10 p-2 rounded-full text-[#00ff88] border border-[#00ff88]/20">
              <Activity size={20} />
            </div>
          </div>
          <div className="mt-4 flex gap-3 z-10">
            <button className="flex-1 bg-white/5 hover:bg-white/10 text-white py-2 rounded-[12px] text-sm border border-white/10 transition-colors">暂停</button>
            <button className="flex-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 py-2 rounded-[12px] text-sm border border-red-500/20 transition-colors">急停</button>
          </div>
        </div>

        {/* Safety Status */}
        <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden shadow-lg min-h-[180px]">
          <div className="glow-bg opacity-50"></div>
          <div className="flex justify-between items-start mb-4 z-10 relative">
            <h3 className="text-sm text-dark-text">安全提示</h3>
            <Shield className="text-brand-500" size={20} />
          </div>
          <div className="space-y-3 z-10 relative">
            <div className="bg-gradient-to-r from-brand-500/20 to-transparent p-3 rounded-[8px] text-sm text-gray-300">
              <span className="font-bold text-brand-500 block text-xs mb-1">注意</span>
              进入产线区域前请穿戴防静电服。
            </div>
            <div className="bg-gradient-to-r from-[#00ff88]/20 to-transparent p-3 rounded-[8px] text-sm text-gray-300">
              <span className="font-bold text-[#00ff88] block text-xs mb-1">正常</span>
              光栅保护系统工作正常。
            </div>
          </div>
        </div>

        {/* Permissions */}
        <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden shadow-lg min-h-[180px]">
          <div className="flex justify-between items-start mb-4 z-10 relative">
            <h3 className="text-sm text-dark-text">控制权与权限</h3>
            <Lock className="text-brand-500" size={20} />
          </div>
          <div className="space-y-4 z-10 relative">
            <div className="flex justify-between items-center py-2 border-b border-white/5">
              <span className="text-sm text-gray-300">远程控制权</span>
              <span className="text-xs bg-brand-900/30 text-brand-400 px-2 py-1 rounded border border-brand-900/50">Engineer_01</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-white/5">
              <span className="text-sm text-gray-300">参数修改锁</span>
              <span className="text-xs text-[#00ff88] flex items-center gap-1"><Lock size={10} /> 已锁定</span>
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-sm text-gray-300">AI 介入等级</span>
              <div className="flex gap-1">
                <div className="w-8 h-1.5 bg-brand-500 rounded-full"></div>
                <div className="w-8 h-1.5 bg-brand-500 rounded-full"></div>
                <div className="w-8 h-1.5 bg-white/10 rounded-full"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-20">
        {/* Logs Table */}
        <div className="lg:col-span-2 bg-dark-card border border-white/10 rounded-[20px] shadow-lg flex flex-col relative overflow-hidden">
          <div className="glow-bg opacity-30"></div>
          <div className="p-5 border-b border-white/10 flex justify-between items-center z-10 relative">
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-brand-500" />
              <h3 className="text-white font-medium">告警与操作日志</h3>
            </div>
            <div className="flex gap-2 text-xs">
              <span className="px-3 py-1 rounded-full bg-brand-600 text-white cursor-pointer shadow-glow">全部</span>
              <span className="px-3 py-1 rounded-full bg-white/5 text-dark-text cursor-pointer hover:bg-white/10 hover:text-white transition-colors">告警</span>
              <span className="px-3 py-1 rounded-full bg-white/5 text-dark-text cursor-pointer hover:bg-white/10 hover:text-white transition-colors">操作</span>
            </div>
          </div>
          <div className="flex-1 overflow-auto p-2 z-10 relative">
            <table className="w-full text-left border-collapse">
              <thead className="text-xs text-dark-text uppercase sticky top-0">
                <tr>
                  <th className="p-3 font-medium">时间</th>
                  <th className="p-3 font-medium">级别</th>
                  <th className="p-3 font-medium">来源</th>
                  <th className="p-3 font-medium">内容</th>
                  <th className="p-3 font-medium">操作人</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-white/5">
                {mockLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 text-gray-400 font-mono text-xs">{log.timestamp}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${log.level === 'info' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                          log.level === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-red-500/10 text-red-500 border-red-500/20'
                        }`}>
                        {log.level}
                      </span>
                    </td>
                    <td className="p-3 text-gray-300">{log.source}</td>
                    <td className="p-3 text-gray-200">{log.message}</td>
                    <td className="p-3 text-gray-500 text-xs">{log.operator || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Comms & Vars */}
        <div className="space-y-8">
          {/* Comms Health */}
          <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 shadow-lg relative overflow-hidden">
            <h3 className="text-sm text-dark-text mb-4 flex items-center gap-2">
              <Server size={18} className="text-brand-500" />
              通讯与接口健康
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center group">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-[#00ff88] shadow-[0_0_8px_#00ff88]"></span>
                  <span className="text-gray-300 text-sm group-hover:text-white transition-colors">PLC 主站心跳</span>
                </div>
                <span className="text-xs text-[#00ff88] font-mono">12ms</span>
              </div>
              <div className="flex justify-between items-center group">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-[#00ff88] shadow-[0_0_8px_#00ff88]"></span>
                  <span className="text-gray-300 text-sm group-hover:text-white transition-colors">MES 接口 (HTTP)</span>
                </div>
                <span className="text-xs text-[#00ff88] font-mono">200 OK</span>
              </div>
              <div className="flex justify-between items-center group">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-yellow-500 shadow-[0_0_8px_#eab308]"></span>
                  <span className="text-gray-300 text-sm group-hover:text-white transition-colors">视觉服务器 B</span>
                </div>
                <span className="text-xs text-yellow-500 font-mono">延迟高</span>
              </div>
              <div className="flex justify-between items-center group">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-[#00ff88] shadow-[0_0_8px_#00ff88]"></span>
                  <span className="text-gray-300 text-sm group-hover:text-white transition-colors">AGV 调度系统</span>
                </div>
                <span className="text-xs text-[#00ff88] font-mono">稳定</span>
              </div>
            </div>
          </div>

          {/* Key Variables */}
          <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 shadow-lg flex-1 relative overflow-hidden">
            <div className="glow-bg opacity-30"></div>
            <h3 className="text-sm text-dark-text mb-4 flex items-center gap-2 relative z-10">
              <Radio size={18} className="text-brand-500" />
              关键变量监控
            </h3>
            <div className="grid grid-cols-2 gap-4 relative z-10">
              <div className="bg-black/40 p-3 rounded-[12px] border border-white/5 hover:border-brand-500/30 transition-colors">
                <span className="text-dark-text text-xs block mb-1">炉温 Zone 1</span>
                <span className="text-white font-mono text-lg font-medium">185.4 °C</span>
              </div>
              <div className="bg-black/40 p-3 rounded-[12px] border border-white/5 hover:border-brand-500/30 transition-colors">
                <span className="text-dark-text text-xs block mb-1">伺服扭矩</span>
                <span className="text-white font-mono text-lg font-medium">42.1 Nm</span>
              </div>
              <div className="bg-black/40 p-3 rounded-[12px] border border-white/5 hover:border-brand-500/30 transition-colors">
                <span className="text-dark-text text-xs block mb-1">总能耗</span>
                <span className="text-white font-mono text-lg font-medium">842 kW/h</span>
              </div>
              <div className="bg-black/40 p-3 rounded-[12px] border border-white/5 hover:border-brand-500/30 transition-colors">
                <span className="text-dark-text text-xs block mb-1">传送带速度</span>
                <span className="text-white font-mono text-lg font-medium">1.2 m/s</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Upward Glow Gradient (Same as Dashboard) */}
      <div className="fixed bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-brand-600/30 to-transparent pointer-events-none z-0"></div>
    </div>
  );
};

export default SafetyOps;