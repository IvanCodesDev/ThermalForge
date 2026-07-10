import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Activity, ArrowUpRight, ArrowRight } from 'lucide-react';
import { RoleTask, RoleType } from '../types';
import aiTrainerImg from '../../data/images/image-removebg-preview (1).png';
import plcEngineerImg from '../../data/images/image-removebg-preview (2).png';
import aiEngineerImg from '../../data/images/image-removebg-preview (3).png';
import robotEngineerImg from '../../data/images/image-removebg-preview (4).png';

const mockProductionData = [
   { time: '08:00', value: 450 },
   { time: '09:00', value: 480 },
   { time: '10:00', value: 520 },
   { time: '11:00', value: 490 },
   { time: '12:00', value: 460 },
   { time: '13:00', value: 510 },
   { time: '14:00', value: 550 },
   { time: '15:00', value: 530 },
   { time: '16:00', value: 580 },
   { time: '17:00', value: 600 },
];

const mockDefectData = [
   { time: '周一', value: 12 },
   { time: '周二', value: 19 },
   { time: '周三', value: 8 },
   { time: '周四', value: 15 },
   { time: '周五', value: 5 },
   { time: '周六', value: 9 },
   { time: '周日', value: 7 },
];

const roles: RoleTask[] = [
   {
      role: RoleType.AI_TRAINER,
      currentTask: "模型训练参数优化",
      progress: 65,
      lastAction: "更新了 AI_Model_02 参数",
      status: 'busy',
      avatar: aiTrainerImg
   },
   {
      role: RoleType.PLC_ENGINEER,
      currentTask: "产线节拍优化逻辑调试",
      progress: 75,
      lastAction: "更新了 PLC_Block_04 参数",
      status: 'idle',
      avatar: plcEngineerImg
   },
   {
      role: RoleType.AI_ENGINEER,
      currentTask: "AI算法部署验证",
      progress: 80,
      lastAction: "部署 AI_Processor_01 模型",
      status: 'busy',
      avatar: aiEngineerImg
   },
   {
      role: RoleType.ROBOT_ENGINEER,
      currentTask: "机器人关节精度校准",
      progress: 45,
      lastAction: "完成 2 号机器人校准",
      status: 'warning',
      avatar: robotEngineerImg
   }
];

const Dashboard: React.FC = () => {
   return (
      <div className="h-full overflow-y-auto pr-2 relative [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
         {/* Quick Status Bar */}
         <div className="grid grid-cols-[1fr_2fr_1fr] bg-dark-card border border-white/10 rounded-[15px] p-4 mb-8 items-center relative overflow-hidden">
            <div className="glow-bg opacity-50"></div>
            <div className="flex items-center gap-3 text-white font-medium z-10">
               <div className="bg-brand-500/20 p-2 rounded-full text-brand-500">
                  <Activity size={18} />
               </div>
               系统状态
            </div>
            <div className="flex justify-center gap-4 z-10">
               <div className="bg-black border border-white/10 px-4 py-2 rounded-[10px] text-sm flex justify-between w-[160px]">
                  <span className="text-dark-text">生产状态</span>
                  <span className="text-white">运行中</span>
               </div>
               <div className="bg-black border border-white/10 px-4 py-2 rounded-[10px] text-sm flex justify-between w-[160px]">
                  <span className="text-dark-text">安全互锁</span>
                  <span className="text-[#00ff88]">已锁定</span>
               </div>
            </div>
            <div className="text-right z-10">
               <button className="text-brand-500 border border-brand-500 bg-transparent px-4 py-1.5 rounded-[20px] text-sm hover:bg-brand-500 hover:text-white transition-colors">
                  生成报告
               </button>
            </div>
         </div>

         <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-20">

            {/* Card 1: Cycle Time (Glow Effect) */}
            <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden flex flex-col justify-between min-h-[240px]">
               <div className="glow-bg"></div>
               <div className="flex justify-between items-start z-10">
                  <div>
                     <div className="text-sm text-dark-text">产线节拍实时监控</div>
                     <div className="flex items-center gap-2 mt-1">
                        <span className="text-2xl font-bold text-[#ff9900]">4.2s</span>
                        <span className="text-xs text-dark-text">目标: 4.5s</span>
                     </div>
                  </div>
                  <button className="bg-brand-500 text-white w-8 h-8 rounded-full flex items-center justify-center shadow-glow">
                     <ArrowUpRight size={16} />
                  </button>
               </div>

               <div className="mt-4 flex-1">
                  <ResponsiveContainer width="100%" height="100%">
                     <AreaChart data={mockProductionData}>
                        <defs>
                           <linearGradient id="colorProd" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#ff5500" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#ff5500" stopOpacity={0} />
                           </linearGradient>
                        </defs>
                        <Area type="monotone" dataKey="value" stroke="#ff5500" strokeWidth={2} fillOpacity={1} fill="url(#colorProd)" />
                     </AreaChart>
                  </ResponsiveContainer>
               </div>

               <div className="flex justify-between text-xs text-dark-text mt-2 z-10">
                  <span>今日</span><span>本周</span><span>本月</span>
               </div>
            </div>

            {/* Card 2: Defect Rate */}
            <div className="bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden flex flex-col min-h-[240px]">
               <div className="glow-bg opacity-30"></div>
               <div className="flex justify-between items-start mb-4 z-10">
                  <span className="text-sm text-dark-text">缺陷率分布</span>
                  <span className="text-sm px-2 py-0.5 bg-gray-800 rounded text-white">0.08%</span>
               </div>

               <div className="flex-1 flex items-end justify-between gap-1 pt-4 z-10">
                  {mockDefectData.map((d, i) => (
                     <div key={i} className="flex-1 flex flex-col justify-end h-full gap-1 group">
                        <div
                           className="w-full bg-gradient-to-t from-brand-500 to-transparent rounded-sm opacity-60 group-hover:opacity-100 transition-all duration-300"
                           style={{ height: `${d.value * 5}%` }}
                        ></div>
                     </div>
                  ))}
               </div>
               <div className="flex justify-between text-[10px] text-dark-text mt-2 z-10">
                  {mockDefectData.map((d, i) => <span key={i}>{d.time}</span>)}
               </div>
            </div>

            {/* Card 3: Promo / Vis Entry */}
            <div className="bg-gradient-to-br from-[#ff5500] to-[#cc2200] rounded-[20px] p-5 relative overflow-hidden flex flex-col justify-end min-h-[240px] text-white group cursor-pointer hover:shadow-glow transition-shadow">
               <div className="absolute top-0 right-0 bottom-0 left-0 bg-[radial-gradient(circle_at_top_right,#ff9900_0%,transparent_60%)] opacity-50"></div>

               <div className="relative z-10">
                  <div className="absolute -top-32 right-0 text-white/20 transform translate-x-4">
                     <ArrowUpRight size={100} />
                  </div>
                  <h2 className="text-2xl font-bold mb-2 uppercase leading-tight">可视化大屏</h2>
                  <p className="text-sm text-white/80 mb-4">查看宏观实时运行数据</p>
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
                     立即进入 <ArrowRight size={14} />
                  </div>
               </div>
            </div>

            {/* Bottom Section: Role List (Asset List style) */}
            <div className="lg:col-span-3 bg-dark-card border border-white/10 rounded-[20px] p-5 relative overflow-hidden">
               <div className="glow-bg"></div>
               <div className="flex gap-4 mb-4 items-center z-10 relative">
                  <button className="bg-brand-500 text-white px-4 py-1.5 rounded-[20px] text-sm shadow-glow font-medium border-none">
                     在线角色
                  </button>
                  <span className="text-sm text-dark-text">实时协同状态</span>
               </div>

               <div className="grid grid-cols-[0.5fr_1.5fr_1fr_1fr_0.5fr] text-sm text-dark-text py-2 border-b border-white/10 relative z-10">
                  <span>角色</span>
                  <span>当前任务</span>
                  <span>进度</span>
                  <span>最近操作</span>
                  <span>状态</span>
               </div>

               <div className="flex flex-col relative z-10">
                  {roles.map((role, idx) => (
                     <div key={idx} className="grid grid-cols-[0.5fr_1.5fr_1fr_1fr_0.5fr] py-4 border-b border-white/5 items-center text-sm last:border-none hover:bg-white/5 transition-colors">
                        <div className="flex items-center gap-3">
                           <div className="w-8 h-8 rounded-full bg-[#333] flex items-center justify-center overflow-hidden border border-brand-500/30">
                              <img src={role.avatar} alt={String(role.role)} className="w-full h-full object-cover" />
                           </div>
                           <span className="font-bold text-white">{role.role}</span>
                        </div>
                        <div className="text-white">{role.currentTask}</div>
                        <div className="pr-10">
                           <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-[#333] rounded-full overflow-hidden">
                                 <div
                                    className="h-full bg-[#00ff88] rounded-full"
                                    style={{ width: `${role.progress}%` }}
                                 ></div>
                              </div>
                              <span className="text-xs text-[#00ff88]">{role.progress}%</span>
                           </div>
                        </div>
                        <div className="text-dark-text truncate pr-4">{role.lastAction}</div>
                        <div>
                           <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${role.status === 'busy' ? 'bg-[#ff5500]/20 text-[#ff5500]' :
                                 role.status === 'idle' ? 'bg-[#00ff88]/20 text-[#00ff88]' :
                                    'bg-yellow-500/20 text-yellow-500'
                              }`}>
                              {role.status === 'busy' ? '忙碌' : role.status === 'idle' ? '空闲' : '待处理'}
                           </span>
                        </div>
                     </div>
                  ))}
               </div>
            </div>

         </div>

         {/* Bottom Upward Glow Gradient */}
         <div className="fixed bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-brand-600/30 to-transparent pointer-events-none z-0"></div>
      </div>
   );
};

export default Dashboard;