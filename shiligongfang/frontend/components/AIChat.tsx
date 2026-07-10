import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, ShieldAlert, CheckSquare, AlertTriangle, FileText, ChevronRight, CheckCircle, MoreHorizontal, Paperclip, Mic, History, MessageSquare } from 'lucide-react';
import { ChatMessage, RoleType } from '../types';

const INITIAL_MESSAGES: ChatMessage[] = [
   {
      id: '1',
      sender: 'ai',
      content: '我是视锂工坊智能助手。我可以协助您查询 SOP、处理设备故障、提供调试建议。请问有什么可以帮您？',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isStructured: false
   }
];

const MOCK_HISTORY = [
   { id: '1', topic: "产线启动异常排查", time: "10:42" },
   { id: '2', topic: "视觉检测阈值参数查询", time: "昨天" },
   { id: '3', topic: "周度产能报表生成", time: "周一" },
   { id: '4', topic: "机械臂关节保养 SOP", time: "周一" },
   { id: '5', topic: "PLC 模块通讯故障", time: "10/24" },
];

const AIChat: React.FC = () => {
   // Chat messages for the currently open session
   const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
   const [input, setInput] = useState('');
   const [isTyping, setIsTyping] = useState(false);
   const messagesEndRef = useRef<HTMLDivElement>(null);
   // Conversation sessions state (left sidebar)
   const [sessions, setSessions] = useState(MOCK_HISTORY);
   const [currentSessionId, setCurrentSessionId] = useState<string>(MOCK_HISTORY[0].id);

   // Map sessionId -> messages for that session
   const [messagesBySession, setMessagesBySession] = useState<Record<string, ChatMessage[]>>(() => {
      const map: Record<string, ChatMessage[]> = {};
      for (const s of MOCK_HISTORY) {
         map[s.id] = s.id === MOCK_HISTORY[0].id ? INITIAL_MESSAGES : [];
      }
      return map;
   });

   const scrollToBottom = () => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
   };

   useEffect(() => {
      scrollToBottom();
   }, [messages]);

   // When currentSessionId changes load its messages into `messages`
   useEffect(() => {
      const sessionMsgs = messagesBySession[currentSessionId] || [];
      // If there's no message yet, seed with a welcome message
      if (sessionMsgs.length === 0) {
         const welcome = {
            id: Date.now().toString(),
            sender: 'ai' as const,
            content: '会话已创建。您可以在此输入问题或操作指令。',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isStructured: false
         } as ChatMessage;
         setMessages([welcome]);
         setMessagesBySession(prev => ({ ...prev, [currentSessionId]: [welcome] }));
      } else {
         setMessages(sessionMsgs);
      }
   }, [currentSessionId, messagesBySession]);

   // 调用AI API的函数
   const callAIApi = async (message: string) => {
      try {
         const response = await fetch('http://localhost:3001/api/chat', {
            method: 'POST',
            headers: {
               'Content-Type': 'application/json',
            },
            body: JSON.stringify({
               message: message,
               sessionId: currentSessionId
            })
         });

         if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
         }

         const data = await response.json();
         return data;
      } catch (error) {
         console.error('API调用失败:', error);
         throw error;
      }
   };

   // 生成结构化数据的函数（基于AI回复内容）
   const generateStructuredData = (userInput: string, aiResponse: string) => {
      // 检查是否为高风险操作
      const isHighRisk = userInput.includes('启动') || userInput.includes('上电') ||
                        userInput.includes('复位') || userInput.includes('停止') ||
                        userInput.includes('重启');

      if (isHighRisk) {
         return {
            problem: `请求执行：${userInput}`,
            steps: [
               "检查急停按钮状态是否复位",
               "确认安全光栅区域无人员逗留",
               "下发 PLC_CMD_01 启动指令",
               "监控 M_State 状态位变化"
            ],
            basis: "SOP-E-2024-05 设备上电标准作业程序 V3.0",
            risks: "机械臂意外移动可能导致人员撞击伤害；瞬间电流过大可能触发保护。",
            role: RoleType.PLC_ENGINEER,
            requiresAuth: true,
            authStatus: 'pending'
         };
      } else {
         return {
            problem: userInput,
            steps: [
               "查阅相关接口文档 Interface_Doc_V2",
               "比对当前运行参数与设定值",
               "如偏差超过 5%，建议重新校准"
            ],
            basis: "通用故障排查手册 Section 4.2",
            risks: "无显著安全风险，建议在停机间隙操作。",
            role: RoleType.AI_ENGINEER,
            requiresAuth: false
         };
      }
   };

   // 根据用户输入内容决定责任人（优先使用已有 structuredData.role，否则根据关键词匹配）
   const assignRoleByContent = (userInput: string, structuredData: any) => {
      // 如果后端已经给出并且是合法角色，保留
      if (structuredData?.role && Object.values(RoleType).includes(structuredData.role)) {
         return structuredData.role;
      }

      const text = (userInput || '').toLowerCase();

      // 3D相机 / 相机 / 摄像头 / 算法平台 -> 人工智能工程技术员
      const aiEngineerKeywords = ['3d', '3d相机', '相机', '摄像头', '视觉', '算法', '算法平台', '模型平台', '算法平台'];
      for (const kw of aiEngineerKeywords) {
         if (text.includes(kw)) return RoleType.AI_ENGINEER;
      }

      // 模型训练 / 训练 -> 人工智能训练师
      const trainerKeywords = ['训练', '模型训练', '训练集', 'finetune', '微调'];
      for (const kw of trainerKeywords) {
         if (text.includes(kw)) return RoleType.AI_TRAINER;
      }

      // PLC 相关 -> PLC工程师
      const plcKeywords = ['plc', '可编程', '西门子', '三菱', '控制器', '上电', '下电', '传送带', '输送带', '皮带', 'conveyor', 'belt'];
      for (const kw of plcKeywords) {
         if (text.includes(kw)) return RoleType.PLC_ENGINEER;
      }

      // 机械臂 / 机器人 -> 机器人工程技术员
      const robotKeywords = ['机械臂', '机器人', '末端', '关节', '伺服', '机器人臂'];
      for (const kw of robotKeywords) {
         if (text.includes(kw)) return RoleType.ROBOT_ENGINEER;
      }

      // 默认返回人工智能工程技术员（更通用）
      return RoleType.AI_ENGINEER;
   };

   const handleSend = async () => {
      if (!input.trim()) return;

      const userMessage = input.trim();
      const newUserMsg: ChatMessage = {
         id: Date.now().toString(),
         sender: 'user',
         content: userMessage,
         timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      // Append to current session messages both locally and in the session map
      setMessages(prev => {
         const next = [...prev, newUserMsg];
         setMessagesBySession(prevMap => ({ ...prevMap, [currentSessionId]: next }));
         return next;
      });
      setInput('');
      setIsTyping(true);

      try {
         // 调用AI API
         const apiResponse = await callAIApi(userMessage);
         // 调试日志：打印后端返回的原始数据，方便定位是否为后端返回了模拟回复
         // （在浏览器控制台查看）
         // eslint-disable-next-line no-console
         console.log('AI API raw response:', apiResponse);

         if (apiResponse.success) {
            // 如果后端返回了结构化 JSON，则采纳为权威来源（不随意覆盖）
            let structuredData;
            if (apiResponse.structured && apiResponse.structuredData) {
               structuredData = apiResponse.structuredData;
            } else {
               // 后端未提供结构化数据，使用前端本地生成逻辑作为回退
               structuredData = generateStructuredData(userMessage, apiResponse.response);
            }

            // 仅在后端未返回或返回不合法时，才根据关键词赋值责任人；否则保留后端提供的负责人
            const roleFromBackend = structuredData?.role;
            const validRoles = Object.values(RoleType);
            if (!roleFromBackend || !validRoles.includes(roleFromBackend)) {
               structuredData.role = assignRoleByContent(userMessage, structuredData);
            }

            // 聊天气泡显示简短摘要（优先使用结构化 summary 字段）
            const bubbleText = structuredData?.summary || structuredData?.problem || apiResponse.response || '已生成结构化诊断方案';

            const aiResponse: ChatMessage = {
               id: (Date.now() + 1).toString(),
               sender: 'ai',
               content: bubbleText,
               timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
               isStructured: true,
               structuredData: structuredData
            };

            setMessages(prev => {
               const next = [...prev, aiResponse];
               setMessagesBySession(prevMap => ({ ...prevMap, [currentSessionId]: next }));
               return next;
            });
         } else {
            // API调用失败，使用错误消息
            const errorResponse: ChatMessage = {
               id: (Date.now() + 1).toString(),
               sender: 'ai',
               content: apiResponse.error || '抱歉，AI服务暂时不可用，请稍后重试。',
               timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
               isStructured: false
            };

            setMessages(prev => {
               const next = [...prev, errorResponse];
               setMessagesBySession(prevMap => ({ ...prevMap, [currentSessionId]: next }));
               return next;
            });
         }
      } catch (error) {
         console.error('发送消息失败:', error);

         // 网络错误或其他异常
         const errorResponse: ChatMessage = {
            id: (Date.now() + 1).toString(),
            sender: 'ai',
            content: '网络连接失败，请检查网络连接后重试。',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isStructured: false
         };

         setMessages(prev => {
            const next = [...prev, errorResponse];
            setMessagesBySession(prevMap => ({ ...prevMap, [currentSessionId]: next }));
            return next;
         });
      } finally {
         setIsTyping(false);
      }
   };

   // Switch to a different session
   const handleSelectSession = (sessionId: string) => {
      setCurrentSessionId(sessionId);
   };

   // Delete a session and its messages
   const handleDeleteSession = (sessionId: string) => {
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      setMessagesBySession(prevMap => {
         const copy = { ...prevMap };
         delete copy[sessionId];
         return copy;
      });
      // If deleting the current session, switch to first available or create a new one
      if (sessionId === currentSessionId) {
         const remaining = sessions.filter(s => s.id !== sessionId);
         if (remaining.length > 0) {
            setCurrentSessionId(remaining[0].id);
         } else {
            // create a new empty session
            const newId = Date.now().toString();
            const newSession = { id: newId, topic: '新会话', time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
            setSessions([newSession]);
            setMessagesBySession(prev => ({ ...prev, [newId]: [] }));
            setCurrentSessionId(newId);
         }
      }
   };

   const handleAuthAction = (msgId: string, action: 'approve' | 'reject') => {
      setMessages(prev => prev.map(msg => {
         if (msg.id === msgId && msg.structuredData) {
            return {
               ...msg,
               structuredData: {
                  ...msg.structuredData,
                  authStatus: action === 'approve' ? 'approved' : 'rejected'
               }
            };
         }
         return msg;
      }));
   };

   return (
      <div className="flex h-full w-full bg-[#050505] relative overflow-hidden font-sans">
         {/* Ambient Background Glows */}
         <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-brand-600/10 blur-[150px] rounded-full pointer-events-none z-0" />
         <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-brand-900/10 blur-[100px] rounded-full pointer-events-none z-0" />

         {/* Container */}
         <div className="flex w-full h-full p-6 gap-6 z-10 relative">

            {/* Left Sidebar - History Session Records */}
            <div className="w-72 flex flex-col gap-4 shrink-0 hidden md:flex">
               <div className="flex items-center justify-between px-2 mb-2">
                  <h3 className="text-gray-400 text-sm font-bold uppercase tracking-wider flex items-center gap-2">
                     <History size={16} /> 历史会话记录
                  </h3>
                  <MoreHorizontal className="text-gray-600 cursor-pointer hover:text-gray-300" size={16} />
               </div>

               <div className="space-y-3">
                  {sessions.map((session) => {
                     const isActive = session.id === currentSessionId;
                     return (
                        <div
                           key={session.id}
                           onClick={() => handleSelectSession(session.id)}
                           className={`group relative p-4 rounded-xl cursor-pointer transition-all duration-300 border ${isActive
                                 ? 'bg-[#141414] border-brand-500/50 shadow-[0_0_15px_rgba(249,115,22,0.1)]'
                                 : 'bg-[#141414]/40 border-white/5 hover:bg-[#1a1a1a] hover:border-white/10'
                              }`}
                        >
                           {/* Active State Background Gradient */}
                           {isActive && (
                              <div className="absolute inset-0 bg-gradient-to-r from-brand-900/10 to-transparent opacity-50 rounded-xl"></div>
                           )}

                           <div className="relative flex gap-3 items-center">
                              <div className={`w-10 h-10 rounded-lg flex items-center justify-center border transition-colors ${isActive
                                    ? 'bg-brand-900/20 border-brand-500/30 text-brand-500'
                                    : 'bg-gray-900 border-gray-800 text-gray-600 group-hover:text-gray-400'
                                 }`}>
                                 <MessageSquare size={18} />
                              </div>
                              <div className="flex-1 min-w-0">
                                 <h4 className={`text-sm font-medium truncate transition-colors ${isActive ? 'text-gray-100' : 'text-gray-400 group-hover:text-gray-300'
                                    }`}>
                                    {session.topic}
                                 </h4>
                                 <span className="text-[10px] text-gray-600 font-mono block mt-1">{session.time}</span>
                              </div>

                              {/* Delete button */}
                              <button
                                 onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteSession(session.id);
                                 }}
                                 className="ml-2 text-xs text-red-400 hover:text-red-300 bg-transparent px-2 py-1 rounded hidden group-hover:inline-block"
                                 aria-label="删除会话"
                              >
                                 删除
                              </button>
                           </div>
                        </div>
                     );
                  })}
               </div>
            </div>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col bg-[#111] rounded-[32px] border border-white/5 shadow-2xl relative overflow-hidden backdrop-blur-sm">

               {/* Header */}
               <div className="h-16 flex items-center justify-between px-8 border-b border-white/5 bg-white/[0.01]">
                  <div className="flex items-center gap-3">
                     <h2 className="text-xl font-bold text-gray-200 tracking-wide">AI 助手</h2>
                     <span className="px-2 py-0.5 rounded text-[10px] bg-brand-900/30 text-brand-400 border border-brand-900/50">Co-Pilot V2.1</span>
                  </div>
                  <div className="flex items-center gap-4">
                     <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]"></div>
                     <span className="text-xs text-gray-500">系统在线</span>
                  </div>
               </div>

               {/* Messages */}
               <div className="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth z-10">
                  {messages.map((msg, index) => (
                     <div key={msg.id} className={`flex w-full ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`flex gap-4 max-w-[80%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>

                           {/* Index Number / Avatar Placeholder */}
                           <div className="shrink-0 flex flex-col items-center gap-2 pt-1">
                              <span className={`text-xs font-mono opacity-30 ${msg.sender === 'user' ? 'text-right' : 'text-left'}`}>
                                 {index + 1}
                              </span>
                           </div>

                           {/* Message Content */}
                           <div className="flex flex-col gap-2">
                              {/* Text Bubble */}
                              <div className={`p-4 rounded-2xl text-sm leading-relaxed backdrop-blur-md border ${msg.sender === 'user'
                                    ? 'bg-brand-600/10 text-gray-100 border-brand-500/20 rounded-tr-none'
                                    : 'bg-white/5 text-gray-300 border-white/5 rounded-tl-none'
                                 }`}>
                                 {msg.content}
                              </div>

                              {/* Structured Data Card (AI Only) */}
                              {msg.isStructured && msg.structuredData && (
                                 <div className="mt-2 bg-[#161616] border border-brand-500/20 rounded-xl overflow-hidden shadow-lg animate-fade-in">
                                    <div className="bg-gradient-to-r from-brand-900/20 to-transparent p-3 border-b border-white/5 flex items-center gap-2">
                                       <FileText size={14} className="text-brand-500" />
                                       <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">结构化诊断方案</span>
                                    </div>
                                    <div className="p-4 space-y-4">

                                       {/* Problem */}
                                       <div className="flex gap-3">
                                          <span className="text-xs text-gray-500 w-16 shrink-0 pt-0.5">问题识别</span>
                                          <span className="text-sm text-gray-200">{msg.structuredData.problem}</span>
                                       </div>

                                       {/* Steps */}
                                       <div className="flex gap-3">
                                          <span className="text-xs text-gray-500 w-16 shrink-0 pt-0.5">SOP 步骤</span>
                                          <div className="flex-1 space-y-2">
                                             {msg.structuredData.steps.map((step, i) => (
                                                <div key={i} className="flex gap-2 text-xs text-gray-400 bg-black/20 p-2 rounded border border-white/5">
                                                   <span className="text-brand-500 font-mono">{i + 1}.</span>
                                                   {step}
                                                </div>
                                             ))}
                                          </div>
                                       </div>

                                       {/* Meta Grid */}
                                       <div className="grid grid-cols-2 gap-3 pt-2">
                                          <div className="bg-brand-900/10 border border-brand-500/10 p-2 rounded">
                                             <span className="text-[10px] text-gray-500 block mb-1">依据</span>
                                             <span className="text-xs text-brand-300 truncate block">{msg.structuredData.basis}</span>
                                          </div>
                                          <div className="bg-brand-900/10 border border-brand-500/10 p-2 rounded">
                                             <span className="text-[10px] text-gray-500 block mb-1">责任人</span>
                                             <div className="flex items-center gap-1 text-xs text-brand-300">
                                                <User size={10} /> {msg.structuredData.role}
                                             </div>
                                          </div>
                                       </div>

                                       {/* Risks */}
                                       <div className="flex gap-3 items-start bg-red-950/20 p-3 rounded border border-red-900/30">
                                          <ShieldAlert size={14} className="text-red-500 shrink-0 mt-0.5" />
                                          <div className="text-xs text-red-400/90 leading-relaxed">
                                             <span className="font-bold block mb-0.5 text-red-400">风险提示</span>
                                             {msg.structuredData.risks}
                                          </div>
                                       </div>

                                       {/* Auth Block removed per user request (UI for double-approval hidden) */}
                                    </div>
                                 </div>
                              )}
                              <span className="text-[10px] text-gray-600 self-end">{msg.timestamp}</span>
                           </div>
                        </div>
                     </div>
                  ))}

                  {isTyping && (
                     <div className="flex justify-start w-full">
                        <div className="flex gap-4 max-w-[80%]">
                           <span className="text-xs font-mono opacity-30 pt-1 text-left">...</span>
                           <div className="p-4 rounded-2xl bg-white/5 border border-white/5 rounded-tl-none">
                              <div className="flex gap-1">
                                 <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"></span>
                                 <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-75"></span>
                                 <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-150"></span>
                              </div>
                           </div>
                        </div>
                     </div>
                  )}
                  <div ref={messagesEndRef} />
               </div>

               {/* Input Area - Floating Bottom */}
               <div className="p-6 pt-0 bg-gradient-to-t from-[#000] via-[#111] to-transparent z-20">
                  <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-1 relative shadow-2xl shadow-black/50 group focus-within:border-brand-500/50 transition-colors">
                     <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                           if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              handleSend();
                           }
                        }}
                        placeholder="输入指令或提问..."
                        className="w-full bg-[#111] rounded-xl text-gray-200 text-sm p-4 focus:outline-none resize-none h-24 placeholder-gray-600 font-sans"
                     />
                     <div className="flex justify-between items-center px-4 py-2 bg-[#1a1a1a] rounded-b-xl">
                        <div className="flex gap-4 text-gray-500">
                           <Paperclip size={18} className="hover:text-brand-500 cursor-pointer transition-colors" />
                           <Mic size={18} className="hover:text-brand-500 cursor-pointer transition-colors" />
                        </div>
                        <button
                           onClick={handleSend}
                           className="bg-gradient-to-r from-brand-600 to-brand-500 text-white px-8 py-2.5 rounded-full text-sm font-medium shadow-[0_4px_20px_rgba(249,115,22,0.4)] hover:shadow-[0_4px_25px_rgba(249,115,22,0.6)] hover:scale-105 transition-all duration-300"
                        >
                           发送
                        </button>
                     </div>
                  </div>
                  <p className="text-[10px] text-gray-600 text-center mt-3 font-mono">
                     AI 生成内容仅供参考，高风险操作请务必执行双人复核流程。
                  </p>
               </div>

            </div>
         </div>

         {/* Bottom Upward Glow Gradient */}
         <div className="fixed bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-brand-600/30 to-transparent pointer-events-none z-0"></div>
      </div>
   );
};

export default AIChat;