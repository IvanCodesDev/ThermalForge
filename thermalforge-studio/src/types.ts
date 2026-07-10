import type { Dispatch } from 'react'
import type {
  ProjectAction,
  StepId,
  ThermalProjectState,
} from './state/projectState'

export interface WorkflowPageProps {
  state: ThermalProjectState
  dispatch: Dispatch<ProjectAction>
  onNavigate: (step: StepId) => void
}
