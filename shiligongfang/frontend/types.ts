export enum RoleType {
  AI_TRAINER = '人工智能训练师',
  PLC_ENGINEER = '自动控制工程技术员',
  AI_ENGINEER = '人工智能工程技术员',
  ROBOT_ENGINEER = '机器人工程技术员'
}

export interface MetricData {
  name: string;
  value: number;
  unit: string;
  trend: 'up' | 'down' | 'stable';
}

export interface ChartData {
  time: string;
  value: number;
  value2?: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  source: 'System' | 'Network' | 'PLC' | 'AI';
  operator?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  content: string;
  timestamp: string;
  isStructured?: boolean;
  structuredData?: {
    problem: string;
    steps: string[];
    basis: string;
    risks: string;
    role: RoleType;
    requiresAuth?: boolean;
    authStatus?: 'pending' | 'approved' | 'rejected';
  };
}

export interface RoleTask {
  role: RoleType;
  currentTask: string;
  progress: number;
  lastAction: string;
  status: 'busy' | 'idle' | 'warning';
  avatar: string;
}