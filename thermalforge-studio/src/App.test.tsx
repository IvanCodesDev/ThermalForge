import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'

describe('ThermalForge workflow', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows the thermal dashboard and Three.js model mount point', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'ThermalForge Studio' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText('待分析').length).toBeGreaterThan(0)
    expect(screen.getByTestId('three-model-viewport')).toBeInTheDocument()
  })

  it('navigates directly between workflow pages from the capsule navigation', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /硬件热源/ }))

    expect(
      screen.getByRole('heading', { name: '选择诊断硬件与主要热源' }),
    ).toBeInTheDocument()
  })

  it('keeps the rescue scenario selected by default', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /场景预选/ }))

    expect(
      screen.getByRole('button', { name: /人形机器人救援任务/ }),
    ).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps every workflow destination reachable from the top navigation', async () => {
    const user = userEvent.setup()
    render(<App />)
    const destinations = [
      ['场景预选', '选择任务场景'],
      ['硬件热源', '选择诊断硬件与主要热源'],
      ['安装约束', '设置安装约束与优化目标'],
      ['结构生成', '生成候选热增强结构'],
      ['性能对比', '热性能对比结果'],
      ['报告导出', '生成热诊断与结构优化报告'],
    ] as const

    const navigation = within(
      screen.getByRole('navigation', { name: '项目工作流' }),
    )
    for (const [navigationLabel, heading] of destinations) {
      await user.click(
        navigation.getByRole('button', { name: new RegExp(navigationLabel) }),
      )
      expect(
        screen.getByRole('heading', { name: heading }),
      ).toBeInTheDocument()
    }
  })

  it('generates output from explicit inputs and invalidates it after input changes', async () => {
    const user = userEvent.setup()
    render(<App />)
    const navigation = within(
      screen.getByRole('navigation', { name: '项目工作流' }),
    )

    await user.click(
      navigation.getByRole('button', { name: /硬件热源/ }),
    )
    const ambientInput = screen.getByRole('spinbutton', {
      name: /环境温度/,
    })
    await user.clear(ambientInput)
    await user.type(ambientInput, '35')

    await user.click(
      navigation.getByRole('button', { name: /性能对比/ }),
    )
    expect(
      screen.getByRole('heading', { name: '尚未运行热分析' }),
    ).toBeInTheDocument()

    await user.click(
      navigation.getByRole('button', { name: /结构生成/ }),
    )
    await user.click(
      screen.getByRole('button', { name: '运行热分析并生成输出' }),
    )
    expect(screen.getByText('输出已生成')).toBeInTheDocument()

    await user.click(
      navigation.getByRole('button', { name: /性能对比/ }),
    )
    expect(screen.getByText('工程估算输出')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: '本次输入生成的温升曲线' }),
    ).toBeInTheDocument()

    await user.click(
      navigation.getByRole('button', { name: /硬件热源/ }),
    )
    const updatedAmbientInput = screen.getByRole('spinbutton', {
      name: /环境温度/,
    })
    await user.clear(updatedAmbientInput)
    await user.type(updatedAmbientInput, '36')
    await user.click(
      navigation.getByRole('button', { name: /性能对比/ }),
    )
    expect(
      screen.getByRole('heading', { name: '尚未运行热分析' }),
    ).toBeInTheDocument()
  })
})
